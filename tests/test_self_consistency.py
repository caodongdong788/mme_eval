"""self-consistency 多采样单测（change decouple-scoring-axes）。

覆盖：
  - K=1 → 单次调用、score_dispersion=0、行为不变
  - K>1 → 逐维度聚合（median / 安全维度 min）+ 离散度（极差）产出
  - self_consistency / aggregate 纳入 fingerprint
"""

from __future__ import annotations

import asyncio

from medeval.judges.llm import LLMJudge
from medeval.models import (
    ChatMessage,
    ConversationTrace,
    Level,
    Rubric,
    RubricItem,
    TestCase,
    Turn,
)


def _case() -> TestCase:
    return TestCase(
        sample_id="sc",
        scenario="t",
        level=Level.L2,
        turns=[Turn(role="user", content="hi")],
        rubric=Rubric(
            empathy=RubricItem(max=4),
            triage_quality=RubricItem(max=4),
        ),
    )


def _trace() -> ConversationTrace:
    return ConversationTrace(
        messages=[ChatMessage(role="assistant", content="answer")]
    )


def _scripted_judge(scripts: list[dict[str, int]], **kwargs) -> LLMJudge:
    """构造一个 enabled 但用脚本化 _call 替换真实 LLM 调用的 LLMJudge。"""
    j = LLMJudge(enabled=False, **kwargs)
    j.enabled = True
    calls = list(scripts)

    async def fake_call(model, prompt):
        scores = calls.pop(0)
        reasons = {k: f"r-{v}" for k, v in scores.items()}
        return scores, reasons, []

    j._call = fake_call  # type: ignore[assignment]
    return j


def test_k1_no_dispersion_single_call():
    j = _scripted_judge([{"empathy": 3, "triage_quality": 2}], self_consistency=1)
    verdicts = asyncio.run(j.judge(_case(), _trace()))
    by = {v.name: v for v in verdicts}
    assert by["llm.empathy"].score == 3.0
    assert by["llm.triage_quality"].score == 2.0
    assert all(v.score_dispersion == 0.0 for v in verdicts)


def test_k3_median_aggregate_and_dispersion():
    # empathy(非安全): median([3,4,3])=3，离散度 max-min=1
    j = _scripted_judge(
        [
            {"empathy": 3, "triage_quality": 2},
            {"empathy": 4, "triage_quality": 1},
            {"empathy": 3, "triage_quality": 2},
        ],
        self_consistency=3,
        aggregate="median",
    )
    verdicts = asyncio.run(j.judge(_case(), _trace()))
    by = {v.name: v for v in verdicts}
    assert by["llm.empathy"].score == 3.0
    assert by["llm.empathy"].score_dispersion == 1.0


def test_safety_sensitive_dim_takes_min():
    # triage_quality 是安全敏感维度：取 min([2,1,2])=1，与 aggregate=median 无关
    j = _scripted_judge(
        [
            {"empathy": 3, "triage_quality": 2},
            {"empathy": 4, "triage_quality": 1},
            {"empathy": 3, "triage_quality": 2},
        ],
        self_consistency=3,
        aggregate="median",
    )
    verdicts = asyncio.run(j.judge(_case(), _trace()))
    by = {v.name: v for v in verdicts}
    assert by["llm.triage_quality"].score == 1.0
    assert by["llm.triage_quality"].score_dispersion == 1.0


def test_self_consistency_changes_fingerprint():
    assert LLMJudge(self_consistency=1).fingerprint() != LLMJudge(
        self_consistency=3
    ).fingerprint()
    assert LLMJudge(aggregate="median").fingerprint() != LLMJudge(
        aggregate="min"
    ).fingerprint()
