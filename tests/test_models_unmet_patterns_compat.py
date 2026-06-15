"""Backwards compatibility for `JudgeVerdict.unmet_patterns`.

旧 report.json（在 change `enrich-must-have-verdict-with-unmet-patterns` 之前生成）
里 verdict 不含 `unmet_patterns` 字段，必须默认 `[]` 加载且不破坏 round-trip。
"""

from __future__ import annotations

from medeval.models import JudgeVerdict, Pattern


def test_legacy_verdict_has_empty_unmet_patterns():
    legacy = {
        "name": "rule.must_have",
        "passed": False,
        "reason": "全部 must_have 均未命中",
    }
    v = JudgeVerdict.model_validate(legacy)
    assert v.unmet_patterns == []


def test_unmet_patterns_serialization_roundtrip():
    v = JudgeVerdict(
        name="rule.must_have",
        passed=False,
        reason="全部 must_have 均未命中（期望任一命中）",
        unmet_patterns=[
            Pattern(keyword="升糖"),
            Pattern(keyword="粗粮"),
            Pattern(regex=r"(白粥|油条).{0,12}(不建议|不推荐)"),
        ],
    )
    js = v.model_dump_json()
    v2 = JudgeVerdict.model_validate_json(js)
    assert len(v2.unmet_patterns) == 3
    assert v2.unmet_patterns[0].keyword == "升糖"
    assert v2.unmet_patterns[2].regex == r"(白粥|油条).{0,12}(不建议|不推荐)"


def test_other_judges_default_empty_unmet_patterns():
    """HardGate / LLM verdict 默认不带 unmet_patterns。"""
    v = JudgeVerdict(
        name="hard_gate.disclaimer",
        passed=False,
        reason="缺少免责声明",
    )
    assert v.unmet_patterns == []


def test_passing_verdict_keeps_empty_unmet_patterns():
    v = JudgeVerdict(
        name="rule.must_have",
        passed=True,
        reason="命中：升糖",
        evidence=["升糖"],
    )
    assert v.unmet_patterns == []
