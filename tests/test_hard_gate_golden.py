"""黄金集回归 —— 直接调 HardGateJudge.judge 验证每条用例的预期 verdict 不变。

修改 hard_gate.py 关键词表后必须本测试全过。新增正/反例时同步更新
``tests/golden/*.yaml``。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from medeval.judges.hard_gate import HardGateJudge
from medeval.models import (
    ChatMessage,
    ConversationTrace,
    TestCase,
    Turn,
)
from tests.golden.schema import GoldenCase, load_golden

_GOLDEN_DIR = Path(__file__).parent / "golden"
_PASS_CASES = load_golden(_GOLDEN_DIR / "hard_gate_should_pass.yaml")
_FAIL_CASES = load_golden(_GOLDEN_DIR / "hard_gate_should_fail.yaml")


def _build_case_trace(g: GoldenCase) -> tuple[TestCase, ConversationTrace]:
    case = TestCase(
        sample_id=g.id,
        scenario="golden",
        level="L1",
        hard_gates=g.hard_gates,
        turns=[Turn(role="user", content=g.user_turn)],
    )
    trace = ConversationTrace(
        messages=[
            ChatMessage(role="user", content=g.user_turn),
            ChatMessage(role="assistant", content=g.bot_reply),
        ],
    )
    return case, trace


def _verdicts_to_map(verdicts) -> dict[str, bool]:
    """把 verdict 列表归一成 {red_flag/no_prescription/disclaimer: passed}."""
    out: dict[str, bool] = {}
    for v in verdicts:
        key = v.name.split(".", 1)[1] if "." in v.name else v.name
        out[key] = v.passed
    return out


@pytest.mark.golden
@pytest.mark.parametrize("g", _PASS_CASES, ids=[g.id for g in _PASS_CASES])
def test_golden_should_pass(g: GoldenCase):
    """每条 pass 用例：expected 中标 pass 的字段，actual 也必须 pass。"""
    case, trace = _build_case_trace(g)
    verdicts = asyncio.run(HardGateJudge().judge(case, trace))
    actual = _verdicts_to_map(verdicts)
    for gate in ("red_flag", "no_prescription", "disclaimer"):
        want = getattr(g.expected, gate)
        if want == "skip":
            continue
        got = actual.get(gate)
        assert got is True, (
            f"[{g.id}] gate={gate} 期望通过，实际 verdicts={actual}\n"
            f"bot_reply 摘录: {g.bot_reply[:80]}..."
        )


@pytest.mark.golden
@pytest.mark.parametrize("g", _FAIL_CASES, ids=[g.id for g in _FAIL_CASES])
def test_golden_should_fail(g: GoldenCase):
    """每条 fail 用例：expected 中标 fail 的字段必须 fail，且期望 tags 是实际 tags 的子集."""
    case, trace = _build_case_trace(g)
    verdicts = asyncio.run(HardGateJudge().judge(case, trace))
    actual = _verdicts_to_map(verdicts)
    for gate in ("red_flag", "no_prescription", "disclaimer"):
        want = getattr(g.expected, gate)
        if want == "skip":
            continue
        got = actual.get(gate)
        if want == "fail":
            assert got is False, (
                f"[{g.id}] gate={gate} 期望 fail，实际通过\nbot_reply: {g.bot_reply[:80]}"
            )
        else:
            assert got is True, (
                f"[{g.id}] gate={gate} 期望 pass，实际 fail"
            )
    # 期望的 failure_tags 必须是实际产出的子集
    actual_tags = {t for v in verdicts for t in v.failure_tags}
    missing = set(g.expected.failure_tags) - actual_tags
    assert not missing, (
        f"[{g.id}] 缺少期望的 failure_tags: {missing}\n实际: {actual_tags}"
    )


def test_golden_pass_and_fail_minimum_size():
    """治理基线：黄金集每边至少 5 条（P0 上线允许较低门槛，后续提升到 30）。"""
    assert len(_PASS_CASES) >= 5
    assert len(_FAIL_CASES) >= 5


def test_golden_all_cases_have_reviewers():
    for case in _PASS_CASES + _FAIL_CASES:
        assert case.reviewed_by, f"[{case.id}] 缺少 reviewed_by"
