from medeval.evaluation import EvaluationDimension
from medeval.judge_labels import (
    FINGERPRINT_LABELS,
    judge_verdict_label,
    judge_verdict_label_map,
)


def test_dimension_and_guideline_labels() -> None:
    assert judge_verdict_label("dimension.medical_safety") == "医学安全性"
    assert judge_verdict_label("dimension.communication") == "沟通体验与继续意愿"
    assert judge_verdict_label("guideline.risk") == "指南·risk"
    assert judge_verdict_label(None) == "-"


def test_unknown_label_is_not_compatibly_rewritten() -> None:
    assert judge_verdict_label("unknown.foo") == "unknown.foo"


def test_label_map_contains_all_eight_dimensions() -> None:
    labels = judge_verdict_label_map()
    for dimension in EvaluationDimension:
        assert f"dimension.{dimension.value}" in labels
    assert FINGERPRINT_LABELS == {
        "dimension": "八维评分",
        "guideline": "指南覆盖评分",
    }
