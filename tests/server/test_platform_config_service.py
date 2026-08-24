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
    comparison = standard["model_comparison"]
    assert len(comparison["dimensions"]) == 8
    assert all(item["max_score"] == 5 for item in comparison["dimensions"])
    assert all(item["score_range"] == "0～5（质量参考）" for item in comparison["dimensions"])
    assert all(item["zero_score_description"] for item in comparison["dimensions"])
    assert all(item["full_score_description"] for item in comparison["dimensions"])


def test_new_judge_labels_are_exposed() -> None:
    labels = platform_config.judge_verdict_labels()
    assert "dimension.medical_safety" in labels
    assert "hard_gate.red_flag" not in labels


def test_failure_tags_include_quality_classifications() -> None:
    labels = platform_config.failure_tag_labels()
    assert labels["adapter_error"] == "Agent 执行失败"
    assert labels["medical_safety_risk"] == "医学安全门禁失败"
    assert labels["clinical_inquiry_gap"] == "关键追问缺失"
    assert labels["plan_feasibility_gap"] == "方案可行性不足"
    assert labels["empathy_gap"] == "情绪承接不足"
    assert labels["executability_gap"] == "行动指引不清"
    assert labels["communication_gap"] == "表达沟通不佳"
    assert labels["guideline_coverage_low"] == "Case 专属要求未充分满足"


def test_evaluation_accounts_have_isolated_pools() -> None:
    config = platform_config.evaluation_accounts()

    assert len(config["accounts"]) == 16
    assert [account["pool"] for account in config["accounts"]].count("stateless") == 8
    assert [account["pool"] for account in config["accounts"]].count("stateful") == 8
    assert all(account["phone"].startswith("+86") for account in config["accounts"])
    # 验证码不再硬编码在仓库中；生产环境通过 Secret 注入。
    assert all(account["verification_code"] == "" for account in config["accounts"])
