"""RuleJudge.unmet_patterns 行为测试。

参见 OpenSpec change `enrich-must-have-verdict-with-unmet-patterns`。
覆盖 OR 全 miss / AND 部分 miss / 通过 / case 无 must_have 四种情形。
"""

from __future__ import annotations

import asyncio

from medeval.judges.rule import RuleJudge
from medeval.models import (
    ChatMessage,
    ConversationTrace,
    ExpectedBehavior,
    Level,
    Pattern,
    TestCase,
    Turn,
)


def _make_case(
    must_have: list[Pattern], must_have_all: bool = False
) -> TestCase:
    return TestCase(
        sample_id="t",
        scenario="s",
        level=Level.L2,
        turns=[Turn(role="user", content="ignored")],
        expected_behavior=ExpectedBehavior(
            must_have=must_have,
            must_have_all=must_have_all,
        ),
    )


def _make_trace(reply: str) -> ConversationTrace:
    return ConversationTrace(
        messages=[
            ChatMessage(role="user", content="ignored"),
            ChatMessage(role="assistant", content=reply),
        ]
    )


def _judge_must_have(case: TestCase, reply: str):
    """同步包装 RuleJudge.judge，并只返回 rule.must_have verdict。"""
    judge = RuleJudge(normalize=True)
    verdicts = asyncio.run(judge.judge(case, _make_trace(reply)))
    return next(v for v in verdicts if v.name == "rule.must_have")


def test_or_all_miss_fills_full_must_have_list():
    must_have = [
        Pattern(keyword="升糖"),
        Pattern(keyword="粗粮"),
        Pattern(regex=r"(白粥|油条).{0,12}(不建议|不推荐)"),
    ]
    case = _make_case(must_have, must_have_all=False)
    v = _judge_must_have(case, "完全无关的回复")
    assert v.passed is False
    assert "全部 must_have 均未命中" in v.reason
    assert "期望任一命中" in v.reason
    assert len(v.unmet_patterns) == 3
    # 顺序保留
    assert v.unmet_patterns[0].keyword == "升糖"
    assert v.unmet_patterns[1].keyword == "粗粮"
    assert v.unmet_patterns[2].regex == r"(白粥|油条).{0,12}(不建议|不推荐)"


def test_or_one_hit_passes_with_empty_unmet():
    must_have = [
        Pattern(keyword="升糖"),
        Pattern(keyword="粗粮"),
    ]
    case = _make_case(must_have, must_have_all=False)
    v = _judge_must_have(case, "建议吃粗粮代替精米。")
    assert v.passed is True
    assert v.unmet_patterns == []


def test_and_partial_miss_fills_only_missing_subset():
    must_have = [
        Pattern(keyword="A"),
        Pattern(keyword="B"),
        Pattern(keyword="C"),
    ]
    case = _make_case(must_have, must_have_all=True)
    v = _judge_must_have(case, "只提到了 B，没说别的。")
    assert v.passed is False
    assert "must_have 部分未命中" in v.reason
    assert "要求全部命中" in v.reason
    # B 被剔除，剩 A、C，按原序
    assert [p.keyword for p in v.unmet_patterns] == ["A", "C"]


def test_and_all_hit_passes_with_empty_unmet():
    must_have = [Pattern(keyword="A"), Pattern(keyword="B")]
    case = _make_case(must_have, must_have_all=True)
    v = _judge_must_have(case, "A 和 B 都说了。")
    assert v.passed is True
    assert v.unmet_patterns == []


def test_no_must_have_returns_na_with_empty_unmet():
    case = _make_case(must_have=[])
    v = _judge_must_have(case, "随便什么回复")
    assert v.passed is True
    assert v.reason == "N/A"
    assert v.unmet_patterns == []
