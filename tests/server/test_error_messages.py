from pydantic import ValidationError

from medeval.models import TestCase
from server.error_messages import format_validation_exception, humanize_error_text


def test_empty_dimension_criteria_has_actionable_chinese_message():
    data = {
        "schema_version": "2.0",
        "sample_id": "error_message_case",
        "scenario": "用例校验",
        "level": "L2",
        "turns": [{"role": "user", "content": "请给我建议"}],
        "evaluation": {
            "dimension_criteria": {
                "professional_accuracy": ["准确说明专业边界"],
            },
            "guidelines": [],
        },
    }
    evaluation = dict(data["evaluation"])
    dimension_criteria = dict(evaluation.get("dimension_criteria") or {})
    dimension_criteria["plan_feasibility"] = {
        "criteria": [],
        "reference_answers": [],
    }
    evaluation["dimension_criteria"] = dimension_criteria
    data["evaluation"] = evaluation

    try:
        TestCase.model_validate(data)
    except ValidationError as exc:
        text = format_validation_exception(exc, prefix="用例校验失败")
    else:  # pragma: no cover - schema must reject the invalid test data
        raise AssertionError("expected validation error")

    assert "方案可行性与依从引导" in text
    assert "至少需要保留 1 条" in text
    assert "validation error" not in text
    assert "pydantic.dev" not in text


def test_unknown_english_error_is_not_exposed():
    assert humanize_error_text("Something unexpected happened") == "操作失败，请稍后重试"


def test_model_internal_error_is_explained_in_chinese():
    text = humanize_error_text(
        "AI 归因生成失败：InternalServerError: An internal error has occurred"
    )
    assert text == "模型服务内部处理失败，请稍后重试；如持续出现，请更换模型或检查模型配置"
