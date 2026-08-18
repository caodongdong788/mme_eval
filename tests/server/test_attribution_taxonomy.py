from __future__ import annotations

import pytest

from server.services.attribution_taxonomy import (
    DOMAIN_COMPONENTS,
    DOMAIN_LABELS,
    SUPPORTED_CAUSE_CODES,
    normalize_optimization_classification,
)
from server.services.case_attribution import _PROMPT


@pytest.mark.parametrize(
    ("code", "domain", "component", "action_type"),
    [
        ("safety_policy_error", "medical_safety", "safety_policy", "safety_rule"),
        ("hook_rule_error", "prompt_hook", "dynamic_hook", "hook_rule"),
        ("context_not_used", "context_memory", "context_usage", "context_injection"),
        ("tool_argument_error", "dialogue_tool_orchestration", "tool_arguments", "tool_schema"),
        ("rag_call_failed", "medical_rag", "rag_service", "rag_service"),
        ("rag_candidate_or_rerank_error", "medical_rag", "rag_candidate", "rerank_config"),
        ("rag_rerank_error", "medical_rag", "rag_rerank", "rerank_config"),
        ("citation_mismatch", "medical_rag", "citation_binding", "citation_binding"),
        ("contraindication_error", "clinical_reasoning", "contraindication", "clinical_reasoning"),
        ("output_protocol_error", "response_delivery", "output_protocol", "response_protocol"),
        ("compaction_error", "model_runtime_observability", "compaction", "runtime_resilience"),
    ],
)
def test_normalizes_every_cx_agent_layer(code, domain, component, action_type):
    result = normalize_optimization_classification(
        {
            "deduction_validation": "supported",
            "primary_cause": {"code": code, "owner": "unknown"},
        }
    )

    assert result == {
        "domain": domain,
        "component": component,
        "failure_mode": code,
        "action_type": action_type,
        "evidence_status": "sufficient",
        "coverage_status": "mapped",
    }


def test_all_eight_cx_agent_domains_have_components():
    assert set(DOMAIN_COMPONENTS) - {"evaluation_system"} == {
        "medical_safety",
        "prompt_hook",
        "context_memory",
        "dialogue_tool_orchestration",
        "medical_rag",
        "clinical_reasoning",
        "response_delivery",
        "model_runtime_observability",
    }
    assert all(DOMAIN_COMPONENTS[domain] for domain in DOMAIN_LABELS)


@pytest.mark.parametrize(
    ("category", "component", "action_type"),
    [
        ("benchmark_criteria_conflict", "benchmark", "evaluation_rule"),
        ("annotation_rag_conflict", "benchmark", "evaluation_rule"),
        ("judge_logic_issue", "judge", "judge_logic"),
    ],
)
def test_evaluation_problems_never_leak_into_cx_agent_domains(category, component, action_type):
    result = normalize_optimization_classification(
        {
            "deduction_validation": "questionable",
            "primary_cause": {"code": "judge_or_benchmark_issue", "owner": "judge"},
        },
        category,
    )

    assert result["domain"] == "evaluation_system"
    assert result["component"] == component
    assert result["action_type"] == action_type


def test_rejects_cross_domain_model_classification():
    result = normalize_optimization_classification(
        {
            "deduction_validation": "supported",
            "primary_cause": {"code": "tool_timeout", "owner": "tool_executor"},
            "optimization_classification": {
                "domain": "medical_rag",
                "component": "rag_rerank",
                "action_type": "evaluation_rule",
            },
        }
    )

    assert result["domain"] == "dialogue_tool_orchestration"
    assert result["component"] == "tool_executor"
    assert result["action_type"] == "tool_executor"


def test_unknown_cause_is_visible_as_taxonomy_gap_instead_of_generic_other():
    result = normalize_optimization_classification(
        {
            "deduction_validation": "supported",
            "primary_cause": {"code": "future_new_failure", "owner": "future_module"},
        }
    )

    assert result["domain"] == "model_runtime_observability"
    assert result["component"] == "taxonomy_gap"
    assert result["coverage_status"] == "unmapped"
    assert result["evidence_status"] == "insufficient"


def test_every_cause_code_offered_to_model_has_a_taxonomy_mapping():
    cause_section = _PROMPT.split("【主要归因类型】", 1)[1].split(
        "【optimization_classification 一级领域】", 1
    )[0]
    prompt_codes = {
        value.strip("。\n ")
        for value in cause_section.replace("\n", "").split("、")
        if value.strip("。\n ")
    }

    assert prompt_codes <= SUPPORTED_CAUSE_CODES
    assert SUPPORTED_CAUSE_CODES - prompt_codes == {"missing_rag_reference"}
