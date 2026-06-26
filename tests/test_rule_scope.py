"""RuleJudge MatchScope（any / last）行为测试。

scope 决定 must_have / output_checks 在哪段回复上判定：
  * any（默认）：所有 assistant 轮拼接后匹配（向后兼容）。
  * last：仅末轮 assistant 回复匹配（记忆 / 末轮综合题）。

must_not_have 是安全禁含红线，恒扫全对话、不受 scope 影响。
"""

from __future__ import annotations

import asyncio

from medeval.judges.rule import RuleJudge
from medeval.models import (
    ChatMessage,
    ConversationTrace,
    ExpectedBehavior,
    Level,
    MatchScope,
    OutputCheck,
    OutputCheckKind,
    Pattern,
    TestCase,
    Turn,
)


def _case(eb: ExpectedBehavior) -> TestCase:
    return TestCase(
        sample_id="t",
        scenario="s",
        level=Level.L2,
        turns=[Turn(role="user", content="ignored")],
        expected_behavior=eb,
    )


def _trace(*assistant_replies: str) -> ConversationTrace:
    """构造多轮 trace：user/assistant 交替，assistant 内容取自入参顺序。"""
    msgs: list[ChatMessage] = []
    for reply in assistant_replies:
        msgs.append(ChatMessage(role="user", content="问"))
        msgs.append(ChatMessage(role="assistant", content=reply))
    return ConversationTrace(messages=msgs)


def _verdict(case: TestCase, trace: ConversationTrace, name: str):
    judge = RuleJudge(normalize=True)
    verdicts = asyncio.run(judge.judge(case, trace))
    return next(v for v in verdicts if v.name == name)


# ── must_have ──────────────────────────────────────────────────────────


def test_must_have_any_matches_earlier_turn():
    """默认 any：关键词出现在前轮即算命中。"""
    eb = ExpectedBehavior(must_have=[Pattern(keyword="来曲唑")])
    v = _verdict(_case(eb), _trace("你在吃来曲唑", "末轮泛泛而谈"), "rule.must_have")
    assert v.passed is True


def test_must_have_last_ignores_earlier_turn():
    """scope=last：前轮命中但末轮缺失 → 判负（记忆召回的核心约束）。"""
    eb = ExpectedBehavior(
        must_have=[Pattern(keyword="来曲唑")], scope=MatchScope.last
    )
    v = _verdict(_case(eb), _trace("你在吃来曲唑", "末轮泛泛而谈"), "rule.must_have")
    assert v.passed is False


def test_must_have_last_matches_last_turn():
    """scope=last：末轮命中 → 通过。"""
    eb = ExpectedBehavior(
        must_have=[Pattern(keyword="来曲唑")], scope=MatchScope.last
    )
    v = _verdict(
        _case(eb), _trace("前轮无关", "末轮串起来曲唑用药史"), "rule.must_have"
    )
    assert v.passed is True


# ── must_not_have 恒扫全对话 ────────────────────────────────────────────


def test_must_not_have_ignores_scope_scans_full():
    """即便 scope=last，禁含词出现在前轮也必须判负（安全红线不漏）。"""
    eb = ExpectedBehavior(
        must_not_have=[Pattern(keyword="不用复查")],
        scope=MatchScope.last,
    )
    v = _verdict(
        _case(eb), _trace("其实你不用复查", "末轮干净"), "rule.must_not_have"
    )
    assert v.passed is False


# ── output_checks 跟随 scope ────────────────────────────────────────────


def test_output_check_last_evaluates_last_reply():
    """scope=last：MAX_CHARS 只对末轮回复计长，不把前轮拼进来。"""
    eb = ExpectedBehavior(
        output_checks=[OutputCheck(kind=OutputCheckKind.MAX_CHARS, params={"max": 5})],
        scope=MatchScope.last,
    )
    # 前轮很长，末轮短 → last 下应通过
    v = _verdict(
        _case(eb), _trace("非常非常非常长的前轮回复", "短"), "rule.output_check0"
    )
    assert v.passed is True
