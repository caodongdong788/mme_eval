from __future__ import annotations

import pytest
from pydantic import ValidationError

from medeval.evaluation import EvaluationDimension
from medeval.models import TestCase


def raw_case() -> dict:
    return {
        "schema_version": "2.0",
        "sample_id": "v2_case",
        "scenario": "症状识别",
        "level": "L2",
        "turns": [{"role": "user", "content": "乳房摸到硬块怎么办？"}],
        "evaluation": {
            "dimension_criteria": {
                "professional_accuracy": ["准确说明风险与诊断边界"],
            },
            "guidelines": [
                {
                    "id": "risk",
                    "dimension": "professional_accuracy",
                    "criterion": "指出硬块需要重视",
                    "max_score": 3,
                }
            ],
        },
    }


def test_v2_schema_accepts_partial_credit_guideline() -> None:
    case = TestCase.model_validate(raw_case())
    point = case.evaluation.guidelines[0]
    assert point.dimension == EvaluationDimension.professional_accuracy
    assert point.max_score == 3
    assert point.criterion == ["指出硬块需要重视"]
    assert point.checkpoints == ["指出硬块需要重视"]
    assert "initial_state" not in case.model_dump(mode="json")


def test_v21_schema_preserves_dimension_and_guideline_reference_answers() -> None:
    raw = raw_case()
    raw["schema_version"] = "2.1"
    raw["evaluation"]["dimension_criteria"] = {
        "professional_accuracy": {
            "criteria": ["准确说明风险与诊断边界"],
            "reference_answers": ["先说明需要尽快就医，再解释不能在线确诊。"],
        }
    }
    raw["evaluation"]["guidelines"] = [{
        "id": "risk",
        "dimension": "professional_accuracy",
        "criteria": ["指出硬块需要重视"],
        "reference_answers": ["建议尽快到乳腺专科检查。"],
        "deduction_rule": "遗漏该要求扣 1 分。",
        "max_score": 3,
    }]

    case = TestCase.model_validate(raw)
    dimension = case.evaluation.dimension_criteria[EvaluationDimension.professional_accuracy]
    guideline = case.evaluation.guidelines[0]

    assert case.schema_version == "2.1"
    assert dimension.criteria == ["准确说明风险与诊断边界"]
    assert dimension.reference_answers == ["先说明需要尽快就医，再解释不能在线确诊。"]
    assert guideline.criteria == ["指出硬块需要重视"]
    assert guideline.reference_answers == ["建议尽快到乳腺专科检查。"]
    assert guideline.deduction_rule == "遗漏该要求扣 1 分。"
    saved = case.model_dump(mode="json")
    assert saved["evaluation"]["dimension_criteria"]["professional_accuracy"]["reference_answers"]
    assert saved["evaluation"]["guidelines"][0]["criteria"] == ["指出硬块需要重视"]


def test_v21_schema_accepts_null_reference_answers_and_old_shapes() -> None:
    case = TestCase.model_validate(raw_case())
    dimension = case.evaluation.dimension_criteria[EvaluationDimension.professional_accuracy]
    assert dimension.criteria == ["准确说明风险与诊断边界"]
    assert dimension.reference_answers == []

    raw = raw_case()
    raw["schema_version"] = "2.1"
    raw["evaluation"]["dimension_criteria"]["professional_accuracy"] = {
        "criteria": ["准确说明风险与诊断边界"],
        "reference_answers": None,
    }
    raw["evaluation"]["guidelines"][0]["reference_answers"] = None
    parsed = TestCase.model_validate(raw)
    assert parsed.evaluation.guidelines[0].reference_answers == []


def test_v2_schema_accepts_list_guideline_and_case_type() -> None:
    raw = raw_case()
    raw["case_type"] = "医学诊疗类"
    raw["is_bug"] = "产品优化"
    raw["evaluation"]["guidelines"][0]["criterion"] = [
        "应追问医生拟开的具体药名。",
        "信息不足时不得直接下结论。",
        "扣分规则：遗漏一项关键要求扣 1 分；遗漏多项关键要求扣 2 分。",
    ]

    case = TestCase.model_validate(raw)
    point = case.evaluation.guidelines[0]

    assert case.case_type == "医学诊疗类"
    assert case.is_bug == "产品优化"
    assert point.checkpoints == ["应追问医生拟开的具体药名。", "信息不足时不得直接下结论。"]
    assert point.deduction_rule.startswith("扣分规则")


def test_v2_schema_keeps_type_as_a_case_type_import_alias() -> None:
    raw = raw_case()
    raw["type"] = "历史类型"

    case = TestCase.model_validate(raw)

    assert case.case_type == "历史类型"
    assert case.model_dump(mode="json")["case_type"] == "历史类型"


def test_v2_schema_accepts_free_profile_and_timeline_initial_state() -> None:
    raw = raw_case()
    raw["initial_state"] = {
        "user_profile": {
            "昵称": "小橙",
            "当前血压": "107/77 mmHg",
            "其他用药": ["来曲唑", "艾普瑞林"],
            "治疗阶段": "内分泌治疗",
        },
        "Timeline": [
            {
                "用药时间": "改到晚上九点服用后，恶心明显减轻",
                "记录日期": "2026-07-01",
            }
        ],
    }

    case = TestCase.model_validate(raw)

    assert case.initial_state.user_profile["昵称"] == "小橙"
    assert case.initial_state.user_profile["当前血压"] == "107/77 mmHg"
    assert case.initial_state.timeline[0]["用药时间"].startswith("改到晚上")
    agent_payload = case.initial_state.to_agent_payload()
    assert agent_payload["user_profile"]["facts"]["治疗阶段"] == "内分泌治疗"
    assert agent_payload["long_term_memories"][0]["label"] == "用药时间"


def test_v2_schema_accepts_arbitrary_chinese_current_concern() -> None:
    raw = raw_case()
    raw["initial_state"] = {
        "user_profile": {
            "current_concern": "乳腺炎（当前状态待确认，可能处于急性期或预防咨询阶段）",
        }
    }

    case = TestCase.model_validate(raw)

    assert case.initial_state.user_profile["current_concern"].startswith("乳腺炎")
    agent_profile = case.initial_state.to_agent_payload()["user_profile"]
    assert "current_concern" not in agent_profile
    assert agent_profile["facts"]["当前关注"].startswith("乳腺炎")


def test_v2_schema_rejects_old_long_term_memories_key() -> None:
    raw = raw_case()
    raw["initial_state"] = {"long_term_memories": []}
    with pytest.raises(ValidationError, match="long_term_memories"):
        TestCase.model_validate(raw)


def test_v2_schema_rejects_metadata_key() -> None:
    raw = raw_case()
    raw["metadata"] = {}
    with pytest.raises(ValidationError, match="metadata"):
        TestCase.model_validate(raw)


def test_v2_schema_rejects_sub_scenario() -> None:
    raw = raw_case()
    raw["sub_scenario"] = "不再属于 Case schema"
    with pytest.raises(ValidationError, match="sub_scenario"):
        TestCase.model_validate(raw)


def test_v2_schema_rejects_guideline_source_key() -> None:
    raw = raw_case()
    raw["evaluation"]["guidelines"][0]["source"] = "不再属于 Case schema"
    with pytest.raises(ValidationError, match="source"):
        TestCase.model_validate(raw)


def test_v2_schema_accepts_free_profile_values() -> None:
    raw = raw_case()
    raw["initial_state"] = {"user_profile": {"任意字段": {"任意嵌套": ["值"]}}}
    case = TestCase.model_validate(raw)
    assert case.initial_state.user_profile["任意字段"]["任意嵌套"] == ["值"]


@pytest.mark.parametrize(
    "legacy_field",
    ["score_profile", "expected_behavior", "hard_gates", "rubric", "scoring_points"],
)
def test_v2_schema_rejects_legacy_scoring_fields(legacy_field: str) -> None:
    raw = raw_case()
    raw[legacy_field] = {} if legacy_field != "scoring_points" else []
    with pytest.raises(ValidationError, match=legacy_field):
        TestCase.model_validate(raw)


def test_schema_version_and_evaluation_are_required() -> None:
    for field in ("schema_version", "evaluation"):
        raw = raw_case()
        raw.pop(field)
        with pytest.raises(ValidationError, match=field):
            TestCase.model_validate(raw)


@pytest.mark.parametrize("max_score", [0, 6, 1.5])
def test_guideline_max_score_is_integer_1_to_5(max_score) -> None:
    raw = raw_case()
    raw["evaluation"]["guidelines"][0]["max_score"] = max_score
    with pytest.raises(ValidationError):
        TestCase.model_validate(raw)


def test_guideline_ids_are_unique() -> None:
    raw = raw_case()
    raw["evaluation"]["guidelines"].append(
        dict(raw["evaluation"]["guidelines"][0])
    )
    with pytest.raises(ValidationError, match="id"):
        TestCase.model_validate(raw)


def test_guideline_cannot_target_binary_safety_dimension() -> None:
    raw = raw_case()
    raw["evaluation"]["guidelines"][0]["dimension"] = "medical_safety"
    with pytest.raises(ValidationError, match="medical_safety"):
        TestCase.model_validate(raw)


def test_old_case_shape_is_rejected_by_loader(tmp_path) -> None:
    from medeval.loader import load_cases
    import yaml

    raw = raw_case()
    raw.pop("schema_version")
    raw.pop("evaluation")
    raw["rubric"] = {"empathy": {"max": 2}}
    path = tmp_path / "old.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        load_cases([str(path)], base_dir=tmp_path)
