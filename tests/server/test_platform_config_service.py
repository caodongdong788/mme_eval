from medeval.evaluation import DIMENSION_STANDARDS, SCORE_ANCHORS, EvaluationDimension
from server.services import platform_config


def test_evaluation_standard_is_complete() -> None:
    standard = platform_config.evaluation_standard()
    assert [item["key"] for item in standard["dimensions"]] == [
        dimension.value for dimension in EvaluationDimension
    ]
    assert standard["dimensions"][0]["binary"] is True
    assert standard["end_max_scores"] == {"doctor": 15, "nurse": 15, "user": 15}
    assert standard["total_max_score"] == 45
    assert standard["guideline_rule"] == "untriggered=0; missing=max_score-score; final=max(0, raw-missing)"
    assert [item["score"] for item in standard["score_anchors"]] == list(SCORE_ANCHORS)
    assert [item["key"] for item in standard["roles"]] == ["doctor", "nurse", "user"]
    assert standard["roles"][1]["raw_max_score"] == 10
    assert standard["roles"][1]["normalized"] is True
    assert standard["dimensions"][2]["full_score_description"] == (
        DIMENSION_STANDARDS[EvaluationDimension.clinical_inquiry]["full_score"]
    )
    assert "重复或过度" in standard["dimensions"][2]["description"]


def test_new_judge_labels_are_exposed() -> None:
    labels = platform_config.judge_verdict_labels()
    assert "dimension.medical_safety" in labels
    assert "hard_gate.red_flag" not in labels


def test_failure_tags_include_quality_classifications() -> None:
    labels = platform_config.failure_tag_labels()
    assert labels["adapter_error"] == "Agent 调用失败"
    assert labels["medical_safety_risk"] == "医学安全风险"
    assert labels["clinical_inquiry_gap"] == "关键追问不足"


def test_evaluation_accounts_have_isolated_pools() -> None:
    config = platform_config.evaluation_accounts()

    assert len(config["accounts"]) == 16
    assert [account["pool"] for account in config["accounts"]].count("stateless") == 8
    assert [account["pool"] for account in config["accounts"]].count("stateful") == 8
    assert all(account["phone"].startswith("+86") for account in config["accounts"])
    assert all(len(account["verification_code"]) == 6 for account in config["accounts"])
