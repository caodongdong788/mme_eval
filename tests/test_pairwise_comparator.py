"""PairwiseComparator 单测（双盲匿名化消偏，OpenSpec change blind-pairwise-debias）。

裁判对**匿名**的「系统①（上）/系统②（下）」判定，输出位置标签 1/2/tie；compare_case 两次
交换「位置↔真实系统」映射并翻译回 A/B 语义。打桩 `_call` 返回裁判原始 JSON：
{"winner": "1"|"2"|"tie", "dimensions": {dim: "1"|"2"|"tie"}, "reason": "...系统①/系统②..."}

两次 pass 的映射（与 compare_case 实现一致）：
  pass1：上=A 下=B → "1"→A、"2"→B
  pass2：上=B 下=A → "1"→B、"2"→A
"""

from __future__ import annotations

import asyncio

from medeval.pairwise import PairwiseComparator, PairwiseResult
from medeval.models import ChatMessage, ConversationTrace, TestCase


def _trace(reply: str) -> ConversationTrace:
    return ConversationTrace(
        messages=[
            ChatMessage(role="user", content="（用户输入）"),
            ChatMessage(role="assistant", content=reply),
        ]
    )


def _case() -> TestCase:
    return TestCase(
        schema_version="2.0",
        sample_id="t_pw",
        scenario="测试",
        level="L2",
        turns=[{"role": "user", "content": "（用户输入）"}],
        evaluation={},
    )


def _make() -> PairwiseComparator:
    return PairwiseComparator(
        provider="openai", model="gpt-4o-mini", api_key="dummy"
    )


def _stub(cmp: PairwiseComparator, responses: list[dict], counter: list | None = None):
    """按调用顺序依次返回 responses 中的裁判 JSON。"""
    seq = list(responses)

    async def fake_call(prompt: str) -> dict:
        if counter is not None:
            counter.append(prompt)
        return seq.pop(0)

    cmp._call = fake_call  # type: ignore[assignment]


def _run(cmp: PairwiseComparator) -> PairwiseResult:
    return asyncio.run(cmp.compare_case(_case(), _trace("A 回复"), _trace("B 回复")))


# ---------------------------------------------------------------------------
# 基本判定（位置标签 → A/B 翻译）


def test_b_clearly_better():
    """两次都判「内容=B 的系统」更优 → winner=B、high。"""
    cmp = _make()
    _stub(
        cmp,
        [
            # pass1 上=A 下=B：判下面(系统②=B) → "2"
            {"winner": "2", "dimensions": {"medical_safety": "2"}, "reason": "系统②给了急诊建议"},
            # pass2 上=B 下=A：判上面(系统①=B) → "1"
            {"winner": "1", "dimensions": {"medical_safety": "1"}, "reason": "系统①给了急诊建议"},
        ],
    )
    res = _run(cmp)
    assert res.winner == "B"
    assert res.confidence == "high"
    assert res.swap_consistent is True
    assert res.dimension_winners.get("medical_safety") == "B"
    assert res.reason == "B给了急诊建议"  # 系统②→B 已翻译


def test_genuine_tie_is_high_confidence():
    cmp = _make()
    _stub(
        cmp,
        [
            {"winner": "tie", "dimensions": {}, "reason": "无差距"},
            {"winner": "tie", "dimensions": {}, "reason": "无差距"},
        ],
    )
    res = _run(cmp)
    assert res.winner == "tie"
    assert res.confidence == "high"
    assert res.swap_consistent is True


# ---------------------------------------------------------------------------
# 位置消偏：双盲下"总判上面的"= 真位置偏见 → 顺序敏感


def test_position_bias_top_downgrades_to_tie():
    """裁判每次都判『在上的系统①』更优（纯位置偏见）→ 翻译回 A/B 相反 → tie/low。"""
    cmp = _make()
    _stub(
        cmp,
        [
            {"winner": "1", "dimensions": {}, "reason": "系统①略好"},  # pass1 1→A
            {"winner": "1", "dimensions": {}, "reason": "系统①略好"},  # pass2 1→B
        ],
    )
    res = _run(cmp)
    assert res.winner == "tie"
    assert res.confidence == "low"
    assert res.swap_consistent is False


def test_swap_consistent_high_confidence():
    """两次都判「内容=A 的系统」更优 → winner=A、high。"""
    cmp = _make()
    _stub(
        cmp,
        [
            {"winner": "1", "dimensions": {"professional_accuracy": "1"}, "reason": "系统①更准确"},  # pass1 1→A
            {"winner": "2", "dimensions": {"professional_accuracy": "2"}, "reason": "系统②更准确"},  # pass2 2→A
        ],
    )
    res = _run(cmp)
    assert res.winner == "A"
    assert res.confidence == "high"
    assert res.swap_consistent is True


# ---------------------------------------------------------------------------
# 医疗保守


def test_dimension_driven_safety_prefers_the_safer_side():
    """总胜方来自八维；即使 raw overall 倾向 B，安全维出现 A 优势时 A 优先。"""
    cmp = _make()
    _stub(
        cmp,
        [
            # pass1 上=A 下=B：整体判 B(=2)，safety 平
            {"winner": "2", "dimensions": {"medical_safety": "tie"}, "reason": "系统②体验好"},
            # pass2 上=B 下=A：整体判 B(=1)，safety 判下面(系统②=A)更好 → B 安全更差
            {"winner": "1", "dimensions": {"medical_safety": "2"}, "reason": "系统①体验好但漏红旗"},
        ],
    )
    res = _run(cmp)
    assert res.winner == "A", "医学安全性优先于 raw overall"
    assert res.confidence == "low", "两次换序维度不一致，仍应待复核"


# ---------------------------------------------------------------------------
# reason 翻译 + order_runs 留痕


def test_reason_relabeled_to_ab():
    cmp = _make()
    _stub(
        cmp,
        [
            # pass1 上=A 下=B：系统②→B、系统①→A
            {"winner": "2", "dimensions": {"executability": "2"}, "reason": "系统②比系统①更早分诊"},
            # pass2 上=B 下=A：系统①→B、系统②→A
            {"winner": "1", "dimensions": {"executability": "1"}, "reason": "系统①比系统②更早分诊"},
        ],
    )
    res = _run(cmp)
    assert res.winner == "B"
    assert res.reason == "B比A更早分诊"
    assert "系统" not in res.reason and "①" not in res.reason


def test_order_runs_records_both_passes():
    """顺序敏感用例 order_runs 留痕两次（top/winner 已映射、reason 已翻译）。"""
    cmp = _make()
    _stub(
        cmp,
        [
            {"winner": "1", "dimensions": {}, "reason": "系统①略好"},  # pass1 top=A, 1→A
            {"winner": "1", "dimensions": {}, "reason": "系统①略好"},  # pass2 top=B, 1→B
        ],
    )
    res = _run(cmp)
    assert len(res.order_runs) == 2
    assert res.order_runs[0]["top"] == "A"
    assert res.order_runs[0]["winner"] == "A"
    assert res.order_runs[0]["reason"] == "A略好"
    assert res.order_runs[1]["top"] == "B"
    assert res.order_runs[1]["winner"] == "B"
    assert res.order_runs[1]["reason"] == "B略好"
    assert "dimension_winners" in res.order_runs[0]


def test_dimension_votes_drive_winner_and_keep_conflicts_visible():
    """总胜负来自八维；同维度 A/B 互相冲突时保守持平，不丢失其他维度的结果。"""
    cmp = _make()
    _stub(
        cmp,
        [
            # pass1：B 在个性化、可执行性胜出。
            {
                "winner": "2",
                "dimensions": {"personalization": "2", "executability": "2"},
                "reason": "系统②更贴合且步骤更清楚",
            },
            # pass2：A 在个性化、共情胜出；可执行性持平。
            {
                "winner": "2",
                "dimensions": {"personalization": "2", "executability": "tie", "empathy": "2"},
                "reason": "系统②更贴合且更有共情",
            },
        ],
    )
    res = _run(cmp)
    assert res.winner == "tie"  # A/B 各有一个有效维度优势
    assert res.confidence == "low"
    assert res.dimension_winners["personalization"] == "tie"  # A/B 都出现过
    assert res.dimension_winners["executability"] == "B"  # B 胜 + tie → B
    assert res.dimension_winners["empathy"] == "A"  # tie + A 胜 → A


# ---------------------------------------------------------------------------
# 双盲 prompt：中性占位、不泄露身份


def test_prompt_is_double_blind():
    cmp = _make()
    prompts: list[str] = []
    _stub(
        cmp,
        [
            {"winner": "tie", "dimensions": {}, "reason": "相当"},
            {"winner": "tie", "dimensions": {}, "reason": "相当"},
        ],
        counter=prompts,
    )
    _run(cmp)
    assert len(prompts) == 2
    for p in prompts:
        assert "系统①" in p and "系统②" in p
        assert "基线" not in p and "本次" not in p
        assert "甲" not in p and "乙" not in p
        # 系统① 在 系统② 之前（①恒在上）
        assert p.index("系统①") < p.index("系统②")


# ---------------------------------------------------------------------------
# 题内并行


def test_inner_swap_calls_run_concurrently():
    cmp = _make()
    in_flight = 0
    peak = 0

    async def fake_call(prompt: str) -> dict:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1
        return {"winner": "tie", "dimensions": {}, "reason": "x"}

    cmp._call = fake_call  # type: ignore[assignment]
    res = _run(cmp)
    assert peak == 2, "两次裁判应并发 in-flight"
    assert res.winner == "tie"


def test_inner_parallel_keeps_semantics():
    cmp = _make()
    _stub(
        cmp,
        [
            {"winner": "2", "dimensions": {"medical_safety": "2"}, "reason": "系统②更稳"},  # pass1 2→B
            {"winner": "1", "dimensions": {"medical_safety": "1"}, "reason": "系统①更稳"},  # pass2 1→B
        ],
    )
    res = _run(cmp)
    assert res.winner == "B"
    assert res.confidence == "high"
    assert res.swap_consistent is True


# ---------------------------------------------------------------------------
# fingerprint


def test_fingerprint_changes_with_model():
    a = PairwiseComparator(model="gpt-4o-mini", api_key="dummy")
    b = PairwiseComparator(model="gpt-4o", api_key="dummy")
    assert a.fingerprint() != b.fingerprint()


def test_fingerprint_ignores_api_key_and_base_url():
    a = PairwiseComparator(model="m", api_key="k1", base_url="http://x")
    b = PairwiseComparator(model="m", api_key="k2", base_url="http://y")
    assert a.fingerprint() == b.fingerprint()
