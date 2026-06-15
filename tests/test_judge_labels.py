"""medeval.judge_labels 单测。"""

from medeval.judge_labels import (
    FINGERPRINT_LABELS,
    judge_verdict_label,
    judge_verdict_label_map,
)


def test_judge_verdict_label_known_pairs():
    assert judge_verdict_label("hard_gate.red_flag") == "硬门槛·红旗分诊"
    assert judge_verdict_label("llm.empathy") == "体验·共情"
    assert judge_verdict_label("hard_gate") == "硬门槛"
    assert judge_verdict_label(None) == "-"


def test_judge_verdict_label_new_rubric_dims():
    assert judge_verdict_label("llm.triage_quality") == "体验·分诊建议"
    assert judge_verdict_label("llm.multi_turn_consistency") == "体验·多轮一致性"


def test_judge_verdict_label_unknown_fallback():
    assert judge_verdict_label("unknown.foo") == "unknown.foo"
    assert judge_verdict_label("rule.output_check0") == "规则·output_check0"


def test_judge_verdict_label_map_contains_keys():
    m = judge_verdict_label_map()
    assert m["hard_gate.red_flag"] == "硬门槛·红旗分诊"
    assert m["llm.triage_quality"] == "体验·分诊建议"
    assert "hard_gate" in m


def test_fingerprint_labels_unchanged():
    assert FINGERPRINT_LABELS["hard_gate"] == "硬门槛 HardGate"
    assert FINGERPRINT_LABELS["llm"] == "LLM 评委"
