from __future__ import annotations

from medeval.assertions import evaluate_assertion, evaluate_assertions
from medeval.models import ConversationTrace, EvaluationAssertion, TestCase


def _case() -> TestCase:
    return TestCase.model_validate(
        {
            "schema_version": "2.1",
            "sample_id": "assertion_case",
            "scenario": "验证工具调用与数据命中的区别",
            "level": "L2",
            "turns": [{"role": "user", "content": "帮我查一下资料"}],
            "evaluation": {"dimension_criteria": {}, "guidelines": []},
        }
    )


def _assertion(kind: str, name: str, min_count: int = 1) -> EvaluationAssertion:
    return EvaluationAssertion(
        id=f"{kind}_{name}",
        type=kind,
        description="测试断言",
        name=name,
        min_count=min_count,
        on_unavailable="fail",
    )


def test_tool_call_passes_but_data_hit_fails_when_search_returns_no_result() -> None:
    trace = ConversationTrace(
        messages=[],
        agent_chain={
            "nodes": [{"name": "medical_literature_search", "type": "TOOL"}],
            "summary": {
                "sources": [
                    {
                        "key": "literature_rag",
                        "label": "医学文献 RAG",
                        "status": "miss",
                        "calls": 1,
                        "count": 0,
                    }
                ]
            },
        },
    )

    tool_result = evaluate_assertion(
        _case(), trace, _assertion("tool_call", "medical_literature_search")
    )
    hit_result = evaluate_assertion(
        _case(), trace, _assertion("retrieval", "literature_rag")
    )

    assert tool_result.passed is True
    assert hit_result.passed is False
    assert hit_result.details["count"] == 0


def test_tool_call_matches_opentelemetry_tool_name_prefix() -> None:
    trace = ConversationTrace(
        messages=[],
        agent_chain={
            "nodes": [
                {
                    "name": "tool.read_medical_metrics",
                    "type": "TOOL",
                    "input": {"names": ["CA15-3", "白细胞"]},
                }
            ]
        },
    )

    result = evaluate_assertion(
        _case(), trace, _assertion("tool_call", "read_medical_metrics")
    )

    assert result.passed is True
    assert result.details["count"] == 1
    assert result.evidence


def test_literature_tool_call_uses_audit_snapshot_when_langfuse_node_is_missing() -> None:
    trace = ConversationTrace(
        messages=[],
        agent_chain={
            "summary": {
                "sources": [
                    {
                        "key": "literature_rag",
                        "label": "医学文献 RAG",
                        "status": "hit",
                        "calls": 2,
                        "count": 20,
                        "snapshot_source": "cx_agent_audit_db",
                    }
                ]
            }
        },
    )

    result = evaluate_assertion(
        _case(), trace, _assertion("tool_call", "medical_literature_search")
    )

    assert result.passed is True
    assert result.details["count"] == 2
    assert result.evidence


def test_literature_tool_call_does_not_pass_without_node_or_audit_call() -> None:
    trace = ConversationTrace(
        messages=[],
        agent_chain={
            "summary": {
                "sources": [
                    {
                        "key": "literature_rag",
                        "label": "医学文献 RAG",
                        "status": "unused",
                        "calls": 0,
                        "count": 0,
                    }
                ]
            }
        },
    )

    result = evaluate_assertion(
        _case(), trace, _assertion("tool_call", "medical_literature_search")
    )

    assert result.passed is False
    assert result.details["count"] == 0


def test_data_hit_uses_confirmed_selected_source_count() -> None:
    trace = ConversationTrace(
        messages=[],
        agent_chain={
            "summary": {
                "sources": [
                    {
                        "key": "literature_rag",
                        "label": "医学文献 RAG",
                        "status": "hit",
                        "calls": 1,
                        "count": 2,
                    }
                ]
            }
        },
    )

    passed = evaluate_assertion(
        _case(), trace, _assertion("retrieval", "literature_rag", min_count=2)
    )
    failed = evaluate_assertion(
        _case(), trace, _assertion("retrieval", "literature_rag", min_count=3)
    )

    assert passed.passed is True
    assert passed.details["count"] == 2
    assert failed.passed is False


def test_legacy_medical_literature_source_name_maps_to_literature_rag() -> None:
    trace = ConversationTrace(
        messages=[],
        agent_chain={
            "summary": {
                "sources": [
                    {
                        "key": "literature_rag",
                        "label": "医学文献 RAG",
                        "status": "hit",
                        "calls": 1,
                        "count": 1,
                    }
                ]
            }
        },
    )

    result = evaluate_assertion(
        _case(), trace, _assertion("retrieval", "medical_literature")
    )

    assert result.passed is True
    assert result.details["count"] == 1


def test_data_hit_counts_successful_read_when_source_has_no_item_count() -> None:
    trace = ConversationTrace(
        messages=[],
        agent_chain={
            "summary": {
                "sources": [
                    {
                        "key": "current_report",
                        "label": "当前报告",
                        "status": "read",
                        "calls": 1,
                        "count": 0,
                    }
                ]
            }
        },
    )

    result = evaluate_assertion(
        _case(), trace, _assertion("retrieval", "current_report")
    )

    assert result.passed is True
    assert result.details["count"] == 1


def test_transcript_answer_requirement_checks_only_final_agent_answer() -> None:
    trace = ConversationTrace(
        messages=[
            {"role": "user", "content": "请回答 CA15-3 是否需要复查"},
            {"role": "assistant", "content": "建议结合后续复查安排观察。"},
        ]
    )
    assertion = EvaluationAssertion(
        id="answer_requirement",
        type="transcript",
        description="最终回答需提及 CA15-3",
        contains="CA15-3",
        scope="assistant_final",
    )

    result = evaluate_assertion(_case(), trace, assertion)

    assert result.passed is False
    assert result.details["scope"] == "assistant_final"
    assert result.details["checked_message_count"] == 1


def test_legacy_transcript_assertion_keeps_full_conversation_scope() -> None:
    trace = ConversationTrace(
        messages=[
            {"role": "user", "content": "请回答 CA15-3 是否需要复查"},
            {"role": "assistant", "content": "建议结合后续复查安排观察。"},
        ]
    )
    assertion = EvaluationAssertion(
        id="legacy_transcript",
        type="transcript",
        description="旧版全文匹配",
        contains="CA15-3",
    )

    result = evaluate_assertion(_case(), trace, assertion)

    assert assertion.scope == "full_conversation"
    assert result.passed is True


def test_semantic_transcript_assertion_is_deferred_to_judge() -> None:
    case = _case()
    case.evaluation.assertions = [
        EvaluationAssertion(
            id="semantic_answer",
            type="transcript",
            description="说明需要复查血常规及其目的",
            contains="提醒用户复查血常规，并说明用于评估治疗安全性",
            scope="assistant_final",
            match_mode="semantic",
            dimension="professional_accuracy",
            deduction=1,
        )
    ]
    trace = ConversationTrace(
        messages=[
            {
                "role": "assistant",
                "content": "建议复查血常规，用于确认当前治疗是否安全。",
            }
        ]
    )

    assert evaluate_assertions(case, trace) == []
