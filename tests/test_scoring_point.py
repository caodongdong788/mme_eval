"""ScoringPointJudge 单测。

覆盖 OpenSpec change add-scoring-point-judge 的核心场景：
  - 空得分点零调用；判官关闭返回空
  - 正负分归一化（含 max_positive==0 边界）
  - grader 失败降级为全部未命中
  - scoring_point.* 软分不阻塞 overall_passed
  - 指南匹配率按点计数派生 / 无锚点记 None
  - fingerprint 随 model/prompt 变、忽略 api_key/base_url

LLM 调用通过 monkeypatch `_call` 打桩，不触网。
"""

from __future__ import annotations

import asyncio

import pytest

from medeval.judges.aggregator import _summarize_verdicts
from medeval.judges.scoring_point import (
    ScoringPointJudge,
    compute_guideline_match_rate,
)
from medeval.models import (
    ChatMessage,
    ConversationTrace,
    JudgeVerdict,
    ScoringPoint,
    TestCase,
)


def _trace(bot_reply: str = "（bot 回复）") -> ConversationTrace:
    return ConversationTrace(
        messages=[
            ChatMessage(role="user", content="（用户输入）"),
            ChatMessage(role="assistant", content=bot_reply),
        ]
    )


def _case(scoring_points=None) -> TestCase:
    return TestCase(
        sample_id="t_sp",
        scenario="测试",
        level="L2",
        turns=[{"role": "user", "content": "（用户输入）"}],
        scoring_points=scoring_points or [],
    )


def _make_judge(**overrides) -> ScoringPointJudge:
    kwargs = dict(enabled=True, provider="openai", model="gpt-4o-mini", api_key="dummy")
    kwargs.update(overrides)
    return ScoringPointJudge(**kwargs)


def _stub(judge: ScoringPointJudge, met_map: dict, counter: list | None = None):
    """met_map: {1-based index: bool}。"""

    async def fake_call(prompt):
        if counter is not None:
            counter.append(1)
        reasons = {i: "stub" for i in met_map}
        return met_map, reasons

    judge._call = fake_call  # type: ignore[assignment]


def _summary(verdicts: list[JudgeVerdict]) -> JudgeVerdict:
    return next(v for v in verdicts if v.name == "scoring_point.summary")


# ---------------------------------------------------------------------------
# 空 / 关闭


def test_empty_scoring_points_zero_call():
    counter: list = []
    judge = _make_judge()
    _stub(judge, {}, counter)
    out = asyncio.run(judge.judge(_case([]), _trace()))
    assert out == []
    assert counter == [], "无得分点不应调用 LLM"


def test_disabled_returns_empty():
    judge = ScoringPointJudge(enabled=False)
    pts = [ScoringPoint(criterion="x", points=2)]
    assert asyncio.run(judge.judge(_case(pts), _trace())) == []


# ---------------------------------------------------------------------------
# 归一化（含负分）


def test_mixed_positive_negative_normalization():
    pts = [
        ScoringPoint(criterion="正分A", points=2),
        ScoringPoint(criterion="正分B", points=1),
        ScoringPoint(criterion="负分C", points=-3),
    ]
    judge = _make_judge()
    # A 命中、B 未命中、C 命中（坏内容出现）
    _stub(judge, {1: True, 2: False, 3: True})
    out = asyncio.run(judge.judge(_case(pts), _trace()))
    s = _summary(out)
    assert s.score == -1.0  # achieved = 2 + 0 + (-3)
    assert s.max_score == 3.0  # max_positive = 2 + 1
    assert not s.passed  # clip(-1/3,0,1) = 0.0


def test_all_positive_full_hit():
    pts = [ScoringPoint(criterion="A", points=2), ScoringPoint(criterion="B", points=3)]
    judge = _make_judge()
    _stub(judge, {1: True, 2: True})
    s = _summary(asyncio.run(judge.judge(_case(pts), _trace())))
    assert s.score == 5.0 and s.max_score == 5.0 and s.passed


def test_only_negative_no_hit_is_full_score():
    pts = [ScoringPoint(criterion="坏内容", points=-3)]
    judge = _make_judge()
    _stub(judge, {1: False})  # 坏内容未出现
    s = _summary(asyncio.run(judge.judge(_case(pts), _trace())))
    assert s.max_score == 0.0
    assert s.passed, "max_positive==0 且无负分命中 → 归一化 1.0"


def test_only_negative_with_hit_is_zero():
    pts = [ScoringPoint(criterion="坏内容", points=-3)]
    judge = _make_judge()
    _stub(judge, {1: True})  # 坏内容出现
    s = _summary(asyncio.run(judge.judge(_case(pts), _trace())))
    assert s.max_score == 0.0
    assert not s.passed, "max_positive==0 且有负分命中 → 归一化 0.0"


# ---------------------------------------------------------------------------
# grader 失败降级


def test_grader_failure_degrades_to_all_unmet():
    pts = [ScoringPoint(criterion="A", points=2)]
    judge = _make_judge()

    async def boom(prompt):
        raise RuntimeError("boom")

    judge._call = boom  # type: ignore[assignment]
    out = asyncio.run(judge.judge(_case(pts), _trace()))
    s = _summary(out)
    assert not s.passed
    assert "失败" in s.reason


# ---------------------------------------------------------------------------
# 软分不阻塞 overall_passed


def test_scoring_point_is_soft_non_blocking():
    """含 scoring_point 的 verdict 列表中，overall 仍只由 hard_gate/rule 决定。"""
    verdicts = [
        JudgeVerdict(name="hard_gate.disclaimer", passed=True),
        JudgeVerdict(name="rule.must_have", passed=True),
        JudgeVerdict(name="scoring_point.summary", passed=False, score=0.0, max_score=5.0),
    ]
    hard_ok, overall, soft, soft_max, tags = _summarize_verdicts(verdicts, _trace())
    assert hard_ok and overall, "得分点低分不得拉挂整题"


# ---------------------------------------------------------------------------
# 指南匹配率派生


def test_guideline_match_rate_by_count():
    pts = [
        ScoringPoint(criterion="A", points=2, guideline="指南/条目1"),
        ScoringPoint(criterion="B", points=2, guideline="指南/条目2"),
        ScoringPoint(criterion="C", points=1),  # 无锚点，不计入
        ScoringPoint(criterion="坏", points=-3, guideline="指南/禁止"),
    ]
    judge = _make_judge()
    # A 命中(达标), B 未命中, 坏内容未出现(负分点达标=未命中)
    _stub(judge, {1: True, 2: False, 3: True, 4: False})
    out = asyncio.run(judge.judge(_case(pts), _trace()))
    rate = compute_guideline_match_rate(_case(pts), out)
    # 带锚点的点：A(达标✓) B(✗) 坏(未出现✓) → 2/3
    assert rate == pytest.approx(2 / 3)


def test_guideline_match_rate_none_without_anchor():
    pts = [ScoringPoint(criterion="A", points=2)]
    judge = _make_judge()
    _stub(judge, {1: True})
    out = asyncio.run(judge.judge(_case(pts), _trace()))
    assert compute_guideline_match_rate(_case(pts), out) is None


# ---------------------------------------------------------------------------
# fingerprint


def test_fingerprint_changes_with_model_ignores_connection():
    assert _make_judge(model="gpt-4o-mini").fingerprint() != _make_judge(
        model="gpt-4o"
    ).fingerprint()
    fp_a = _make_judge(model="gpt-4o-mini", api_key="A", base_url="").fingerprint()
    fp_b = _make_judge(
        model="gpt-4o-mini", api_key="B", base_url="https://x.test"
    ).fingerprint()
    assert fp_a == fp_b


# ---------------------------------------------------------------------------
# schema 校验：零分点被拒


def test_zero_points_rejected():
    with pytest.raises(Exception):
        ScoringPoint(criterion="x", points=0)
