from server.services.case_export import _restore_guideline_dimensions


def test_case_detail_restores_missing_guideline_dimension_from_frozen_case():
    detail = {
        "case": {
            "evaluation": {
                "guidelines": [
                    {"id": "g04", "dimension": "professional_accuracy"},
                    {"id": "g05", "dimension": "clinical_inquiry"},
                ]
            }
        },
        "guideline_scores": [
            {"id": "g04", "dimension": "", "score": 0, "max_score": 1},
            {"id": "g05", "score": 1, "max_score": 1},
            {"id": "g99", "dimension": "", "score": 0, "max_score": 1},
        ],
    }

    result = _restore_guideline_dimensions(detail)

    assert result["guideline_scores"][0]["dimension"] == "professional_accuracy"
    assert result["guideline_scores"][1]["dimension"] == "clinical_inquiry"
    # 没有冻结真值时保持为空，不将未知扣分项错误归类到某个维度。
    assert result["guideline_scores"][2]["dimension"] == ""
