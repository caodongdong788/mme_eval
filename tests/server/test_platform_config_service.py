from medeval.evaluation import EvaluationDimension
from server.services import platform_config


def test_evaluation_standard_is_complete() -> None:
    standard = platform_config.evaluation_standard()
    assert [item["key"] for item in standard["dimensions"]] == [
        dimension.value for dimension in EvaluationDimension
    ]
    assert standard["dimensions"][0]["binary"] is True
    assert standard["end_max_scores"] == {"doctor": 15, "nurse": 15, "user": 15}
    assert standard["total_max_score"] == 45
    assert standard["guideline_rule"] == "missing=max_score-score; final=max(0, raw-missing)"


def test_new_judge_labels_are_exposed() -> None:
    labels = platform_config.judge_verdict_labels()
    assert "dimension.medical_safety" in labels
    assert "hard_gate.red_flag" not in labels


def test_only_infrastructure_failure_tag_remains() -> None:
    assert platform_config.failure_tag_labels() == {"adapter_error": "调用失败"}
