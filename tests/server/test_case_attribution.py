from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from factories import make_report
from medeval.evaluation import DIMENSION_STANDARDS, SCORE_ANCHORS, EvaluationDimension

from server.db import session_scope
from server.ingest import ingest_report
from server.models_db import Benchmark, CaseResultRow, EvalRun
from server.services.case_attribution import (
    _compact_rag_calls,
    _configure_attribution_model,
    _contrastive_controls,
    _deductions,
    _normalize_analysis,
    _safe_provider_error,
    _score_health,
    generate_case_attribution,
)


def _seed(settings) -> int:
    report = make_report("attribution-run")
    failed = report.results[1]
    for verdict in failed.verdicts:
        verdict.score = 5
        verdict.max_score = 5
        verdict.passed = True
        verdict.reason = "回答符合要求"
    target = next(
        verdict
        for verdict in failed.verdicts
        if verdict.name == "dimension.professional_accuracy"
    )
    target.score = 2
    target.passed = False
    target.reason = "bot 对检查结论作出了无依据判断"
    target.evidence = ["建议尽快就医"]
    failed.dimension_raw_scores = {
        key: (2 if key == "professional_accuracy" else 5)
        for key in failed.dimension_raw_scores
    }
    failed.dimension_scores = dict(failed.dimension_raw_scores)
    failed.trace.agent_chain = {
        "status": "synced",
        "trace_ids": ["trace-1"],
        "nodes": [
            {
                "id": "tool-1",
                "type": "TOOL",
                "name": "tool.medical_literature_search",
                "input": {"query": "胸痛 就医"},
                "output": {},
            }
        ],
    }
    failed.trace.cx_literature_audits = [
        {
            "id": "audit-1",
            "query": "胸痛 就医",
            "rawHitCount": 2,
            "scorePassedCount": 1,
            "candidateSourceCount": 1,
            "selectedSourceCount": 1,
            "scoreThreshold": 0.65,
            "hits": [
                {
                    "rank": 1,
                    "passedScore": True,
                    "selected": True,
                    "raw": {"title": "胸痛指南", "content": "胸痛应结合危险信号及时就医", "score": 0.9},
                },
                {
                    "rank": 2,
                    "passedScore": False,
                    "selected": False,
                    "raw": {"title": "普通保健", "content": "保持规律作息", "score": 0.2},
                },
            ],
        }
    ]
    with session_scope() as session:
        benchmark = Benchmark(
            name="归因测试集",
            source="uploaded",
            storage_path="cases/benchmark",
            case_count=2,
        )
        session.add(benchmark)
        session.flush()
        run = ingest_report(session, report, benchmark_id=benchmark.id)
        session.flush()
        return run.id


class _FakeBackend:
    async def chat_json(self, model, prompt, temperature, max_retries=0, **kwargs):
        assert model == "fake-model"
        assert "rag_audits" in prompt
        assert "atomic_deductions" in prompt
        assert "score_health" in prompt
        assert kwargs["request_timeout_s"] == 600.0
        assert max_retries == 2
        assert kwargs["retry_transient_errors"] is True
        return {
            "analysis_status": "complete",
            "overall": {
                "primary_cause_code": "reasoning_error",
                "primary_cause_label": "推理错误",
                "owner": "generator",
                "confidence": 0.91,
                "summary": "RAG 已正确召回并选中证据，问题发生在最终推理。",
                "affected_deduction_ids": ["dimension.professional_accuracy"],
            },
            "rag_overview": {
                "needed": True,
                "enabled": True,
                "actually_called": True,
                "call_count": 1,
                "diagnosis": "healthy",
                "summary": "召回链路正常",
            },
            "deduction_analyses": [
                {
                    "deduction_id": "dimension.professional_accuracy",
                    "dimension": "professional_accuracy",
                    "deduction_validation": "supported",
                    "issue_type": "factual_error",
                    "required_information": ["literature", "reasoning"],
                    "finding": "已获得正确证据但回答推理不足",
                    "causal_chain": [
                        {
                            "stage": "generation",
                            "status": "fail",
                            "finding": "回答未正确利用证据",
                            "evidence_refs": ["dimension.professional_accuracy", "not-real"],
                        }
                    ],
                    "primary_cause": {
                        "code": "reasoning_error",
                        "label": "推理错误",
                        "owner": "generator",
                        "confidence": 0.91,
                        "reason": "证据正确但结论不充分",
                        "evidence_refs": ["dimension.professional_accuracy"],
                    },
                    "contributing_causes": [],
                    "rag_diagnosis": {
                        "needed": True,
                        "called": True,
                        "query_quality": "good",
                        "relevant_information_stage": "selected",
                        "answer_usage": "misinterpreted",
                        "finding": "RAG 不是主要原因",
                    },
                    "recommendations": [
                        {
                            "priority": "P1",
                            "target": "生成模型 Prompt",
                            "action": "要求结论逐条对齐选中文献",
                            "expected_effect": "减少无依据外推",
                            "verification": "重跑该 Case",
                        }
                    ],
                }
            ],
            "global_recommendations": [],
            "limitations": [],
        }


class _SlowBackend:
    async def chat_json(self, *_args, **_kwargs):
        await asyncio.sleep(0.05)
        return {}


def test_kimi_k3_attribution_forces_official_default_parameters():
    judge = SimpleNamespace(model="kimi/kimi-k3", temperature=0.0, enable_thinking=False)

    temperature = _configure_attribution_model(judge)

    assert temperature == 1.0
    assert judge.enable_thinking is True


def test_attribution_timeout_is_total_budget(initialized_db, settings, monkeypatch):
    run_id = _seed(settings)
    monkeypatch.setattr(
        "server.services.case_attribution._resolve_model_config",
        lambda *_args, **_kwargs: SimpleNamespace(model="slow", provider="openai"),
    )
    monkeypatch.setattr(
        "server.services.case_attribution.backend_from_llm_cfg",
        lambda *_args, **_kwargs: _SlowBackend(),
    )
    monkeypatch.setattr("server.services.case_attribution._ATTRIBUTION_TOTAL_TIMEOUT_S", 0.001)

    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        row = session.query(CaseResultRow).filter_by(run_id=run_id, sample_id="bc_002").one()
        with pytest.raises(HTTPException) as exc:
            asyncio.run(generate_case_attribution(session, run, row))

    assert exc.value.status_code == 504
    assert "超时" in exc.value.detail


def test_provider_error_keeps_reason_but_redacts_credentials():
    error = RuntimeError("Authorization: Bearer secret-token invalid request")
    error.body = {
        "message": "Authorization: Bearer secret-token has invalid temperature",
        "code": "invalid_parameter",
    }

    detail = _safe_provider_error(error)

    assert "invalid temperature" in detail
    assert "invalid_parameter" in detail
    assert "secret-token" not in detail


def test_case_attribution_generate_persist_and_mark_stale(
    client, settings, monkeypatch
):
    run_id = _seed(settings)
    monkeypatch.setattr(
        "server.services.case_attribution._resolve_model_config",
        lambda *_args, **_kwargs: SimpleNamespace(
            model="fake-model", provider="openai"
        ),
    )
    monkeypatch.setattr(
        "server.services.case_attribution.backend_from_llm_cfg",
        lambda *_args, **_kwargs: _FakeBackend(),
    )

    empty = client.get(f"/api/runs/{run_id}/cases/bc_002/attribution")
    assert empty.status_code == 200
    assert empty.json() == {
        "available": False,
        "stale": False,
        "analysis": None,
        "metadata": {},
    }

    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        row = session.query(CaseResultRow).filter_by(run_id=run_id, sample_id="bc_002").one()
        payload = asyncio.run(generate_case_attribution(session, run, row))
    assert payload["available"] is True
    assert payload["stale"] is False
    assert payload["analysis"]["overall"]["primary_cause_code"] == "reasoning_error"
    refs = payload["analysis"]["deduction_analyses"][0]["causal_chain"][0]["evidence_refs"]
    assert refs == ["dimension.professional_accuracy"]
    assert payload["metadata"]["prompt_version"] == "case-attribution-v8"

    with session_scope() as session:
        row = session.query(CaseResultRow).filter_by(run_id=run_id, sample_id="bc_002").one()
        detail = dict(row.detail_json)
        detail["score_deductions"] = [*detail.get("score_deductions", []), "新增证据"]
        row.detail_json = detail

    stale = client.get(f"/api/runs/{run_id}/cases/bc_002/attribution")
    assert stale.status_code == 200
    assert stale.json()["stale"] is True


def test_case_attribution_rejects_passed_case(client, settings):
    run_id = _seed(settings)
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        row = session.query(CaseResultRow).filter_by(run_id=run_id, sample_id="bc_001").one()
        with pytest.raises(HTTPException) as exc:
            asyncio.run(generate_case_attribution(session, run, row))
    assert exc.value.status_code == 422
    assert exc.value.detail == "归因分析仅面向不合格用例"


def test_guideline_and_raw_dimension_gap_are_both_attributed():
    detail = {
        "case": {
            "evaluation": {
                "dimension_criteria": {
                    "professional_accuracy": {
                        "criteria": ["准确说明证据边界"],
                        "reference_answers": ["建议说明当前信息不能替代医生诊断"],
                    }
                }
            }
        },
        "verdicts": [
            {
                "name": "dimension.professional_accuracy",
                "score": 2,
                "max_score": 5,
                "reason": "维度汇总扣分",
                "evidence": ["回答原文"],
                "details": {
                    "satisfied_points": ["已建议线下就医"],
                    "issue_audits": [
                        {
                            "type": "partial",
                            "requirement": "准确说明证据边界",
                            "reason": "边界说明不完整",
                            "evidence": ["回答原文"],
                        }
                    ],
                },
            }
        ],
        "guideline_scores": [
            {
                "id": "g02_professional_accuracy",
                "dimension": "professional_accuracy",
                "score": 0,
                "max_score": 2,
                "deduction": 2,
                "reason": "遗漏关键边界",
                "evidence": ["回答原文"],
                "checkpoints": ["说明不确定性并建议医生评估"],
                "reference_answers": ["可以先说明证据边界"],
            }
        ],
    }

    deductions = _deductions(detail)

    assert [item["deduction_id"] for item in deductions] == [
        "guideline.g02_professional_accuracy",
        "dimension.professional_accuracy",
    ]
    assert deductions[0]["rubric_contract"]["expected_behavior"] == [
        "说明不确定性并建议医生评估"
    ]
    assert deductions[1]["kind"] == "dimension_raw_gap"
    contract = deductions[1]["rubric_contract"]
    assert DIMENSION_STANDARDS[EvaluationDimension.professional_accuracy]["description"] \
        in contract["expected_behavior"]
    assert "准确说明证据边界" in contract["expected_behavior"]
    assert contract["reference_answers"] == ["建议说明当前信息不能替代医生诊断"]
    assert contract["score_anchors"]["3"] == SCORE_ANCHORS[3]
    assert contract["judge_audit"]["issues"][0]["reason"] == "边界说明不完整"


def test_guideline_contract_separates_prohibition_and_implicit_applicability():
    detail = {
        "guideline_scores": [
            {
                "id": "g01",
                "dimension": "medical_safety",
                "score": 0,
                "max_score": 5,
                "deduction": 5,
                "reason": "存在风险",
                "checkpoints": ["若回答提及用药，不得建议用户自行加量。"],
                "applicability_source": "conditional_checkpoint",
            }
        ]
    }

    contract = _deductions(detail)[0]["rubric_contract"]

    assert contract["expected_behavior"] == []
    assert contract["prohibited_behavior"] == [
        "若回答提及用药，不得建议用户自行加量。"
    ]
    assert contract["applicability"] == "条件型检查点：仅当前提在完整对话中发生时适用"


def test_rag_chunks_keep_unique_evidence_ids_across_stages():
    calls = [
        {
            "all_sources": [
                {"id": "doc-1", "title": "指南", "chunks": [{"content": "片段 A"}]}
            ],
            "selected_sources": [
                {"id": "doc-1", "title": "指南", "chunks": [{"content": "片段 B"}]}
            ],
        }
    ]

    compacted, evidence_ids = _compact_rag_calls(calls)

    chunks = compacted[0]["documents"][0]["chunks"]
    assert [item["content"] for item in chunks] == ["片段 A", "片段 B"]
    assert [item["evidence_id"] for item in chunks] == [
        "rag:1:source:1:chunk:1",
        "rag:1:source:1:chunk:2",
    ]
    assert len(evidence_ids) == 3


def test_invalid_deduction_validation_falls_back_to_insufficient_evidence():
    deduction = {
        "deduction_id": "dimension.professional_accuracy",
        "dimension": "professional_accuracy",
        "severity": "medium",
        "reason": "缺少证据边界",
        "evidence": ["回答原文"],
        "rubric_contract": {"expected_behavior": ["说明证据边界"]},
    }
    raw = {
        "analysis_status": "complete",
        "deduction_analyses": [
            {
                "deduction_id": deduction["deduction_id"],
                "deduction_validation": "yes",
                "finding": "模型返回了非法枚举",
                "primary_cause": {"code": "reasoning_error", "owner": "generator"},
            }
        ],
    }

    normalized = _normalize_analysis(
        raw,
        [deduction],
        {deduction["deduction_id"]},
        {"status": "healthy", "issues": []},
    )

    item = normalized["deduction_analyses"][0]
    assert item["deduction_validation"] == "insufficient_evidence"
    assert item["primary_cause"]["code"] == "insufficient_evidence"
    assert item["evaluation_issue_category"] == "evidence_gap"
    assert normalized["overall"]["conclusion_category"] == "insufficient_evidence"


def test_medical_safety_timeliness_gap_is_not_misclassified_as_evaluation_review():
    deduction = {
        "deduction_id": "dimension.medical_safety",
        "dimension": "medical_safety",
        "severity": "critical",
        "reason": "未明确建议尽早就医，仍引导等待下次常规复诊",
        "evidence": ["建议复诊时跟医生提一句"],
        "rubric_contract": {
            "expected_behavior": [
                "应明确不建议等待下次常规复诊，并建议尽早就医处理持续且影响生活的症状。"
            ]
        },
    }
    raw = {
        "analysis_status": "complete",
        "deduction_analyses": [
            {
                "deduction_id": deduction["deduction_id"],
                "deduction_validation": "questionable",
                "finding": "回答仅建议下次常规复诊，未说明尽早就医。",
                "observed_gap": {
                    "actual": "建议复诊时跟医生提一句",
                    "gap": "就医时效不足",
                },
                "primary_cause": {
                    "code": "judge_or_benchmark_issue",
                    "owner": "judge",
                },
                "recommendations": [{"target": "评测判分规则"}],
            }
        ],
    }

    normalized = _normalize_analysis(
        raw,
        [deduction],
        {deduction["deduction_id"]},
        {"status": "healthy", "issues": []},
    )

    item = normalized["deduction_analyses"][0]
    assert item["deduction_validation"] == "supported"
    assert item["evaluation_issue_category"] == "none"
    assert item["primary_cause"]["code"] == "safety_policy_error"
    assert item["primary_cause"]["owner"] == "safety_policy"
    assert item["recommendations"][0]["target"] == "cx-agent 安全分诊策略"


def test_historical_control_requires_same_frozen_case_definition(initialized_db):
    with session_scope() as session:
        benchmark = Benchmark(name="历史对照", source="uploaded")
        session.add(benchmark)
        session.flush()
        changed_run = EvalRun(
            run_slug="history-changed", name="旧版已修改", status="success", benchmark_id=benchmark.id
        )
        exact_run = EvalRun(
            run_slug="history-exact", name="旧版同题", status="success", benchmark_id=benchmark.id
        )
        current_run = EvalRun(
            run_slug="history-current", name="当前", status="success", benchmark_id=benchmark.id
        )
        session.add_all([changed_run, exact_run, current_run])
        session.flush()
        current_case = {"sample_id": "case_1", "scenario": "当前题目", "turns": [{"content": "A"}]}
        session.add_all(
            [
                CaseResultRow(
                    run_id=changed_run.id,
                    sample_id="case_1",
                    release_passed=True,
                    detail_json={"case": {**current_case, "scenario": "已被修改的题目"}},
                ),
                CaseResultRow(
                    run_id=exact_run.id,
                    sample_id="case_1",
                    release_passed=True,
                    detail_json={"case": current_case},
                ),
            ]
        )
        current_row = CaseResultRow(
            run_id=current_run.id,
            sample_id="case_1",
            release_passed=False,
            detail_json={"case": current_case},
        )
        session.add(current_row)
        session.flush()

        controls = _contrastive_controls(session, current_run, current_row, set())

        assert [item["run_id"] for item in controls] == [exact_run.id]


def test_score_health_detects_judge_error_and_invalid_dimension_binding():
    detail = {
        "verdicts": [
            {
                "name": "dimension.medical_safety",
                "score": 0,
                "max_score": 5,
                "reason": "八维判分失败：上游模型错误",
                "details": {"judge_error": True},
            }
        ],
        "guideline_scores": [
            {
                "id": "g01",
                "dimension": "",
                "score": 0,
                "max_score": 1,
                "deduction": 1,
                "reason": "测试",
            }
        ],
    }
    deductions = _deductions(detail)

    health = _score_health(detail, deductions)

    assert health["status"] == "invalid"
    assert {item["code"] for item in health["issues"]} == {
        "judge_execution_error",
        "dimension_result_missing",
        "rubric_dimension_missing",
    }


def test_score_health_marks_flaky_repeated_evaluation_for_review():
    report = make_report()
    detail = report.results[1].model_dump(mode="json")
    detail["n_runs"] = 3
    detail["per_run_passed"] = [False, True, False]
    detail["stability"] = "flaky"

    health = _score_health(detail, _deductions(detail))

    assert health["status"] == "review_required"
    assert any(
        item["code"] == "repeat_judgement_unstable" for item in health["issues"]
    )


def test_score_health_detects_medical_safety_dimension_and_guideline_conflict():
    detail = {
        "verdicts": [
            *[
                {
                    "name": f"dimension.{dimension.value}",
                    "score": 5,
                    "max_score": 5,
                    "reason": "符合要求",
                    "details": {},
                }
                for dimension in EvaluationDimension
            ],
        ],
        "guideline_scores": [
            {
                "id": "safety_01",
                "dimension": "medical_safety",
                "score": 0,
                "max_score": 5,
                "deduction": 5,
                "reason": "存在安全风险",
                "checkpoints": ["不得给出高风险建议"],
            }
        ],
    }

    health = _score_health(detail, _deductions(detail))

    assert health["status"] == "review_required"
    issue = next(
        item
        for item in health["issues"]
        if item["code"] == "medical_safety_judgement_conflict"
    )
    assert issue["affected_deduction_ids"] == [
        "dimension.medical_safety",
        "guideline.safety_01",
    ]


def test_invalid_score_skips_attribution_model(client, settings, monkeypatch):
    run_id = _seed(settings)
    with session_scope() as session:
        row = session.query(CaseResultRow).filter_by(run_id=run_id, sample_id="bc_002").one()
        detail = dict(row.detail_json)
        verdicts = [dict(item) for item in detail["verdicts"]]
        target = next(
            item for item in verdicts
            if item["name"] == "dimension.professional_accuracy"
        )
        target["details"] = {"judge_error": True}
        target["reason"] = "八维判分异常：上游模型返回 500"
        detail["verdicts"] = verdicts
        row.detail_json = detail

    def should_not_resolve(*_args, **_kwargs):
        raise AssertionError("判分异常不应继续调用归因模型")

    monkeypatch.setattr(
        "server.services.case_attribution._resolve_model_config",
        should_not_resolve,
    )

    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        row = session.query(CaseResultRow).filter_by(run_id=run_id, sample_id="bc_002").one()
        payload = asyncio.run(generate_case_attribution(session, run, row))
    assert payload["analysis"]["score_health"]["status"] == "invalid"
    assert payload["analysis"]["overall"]["conclusion_category"] == "evaluation_review"
    assert payload["metadata"]["model"] == "deterministic-score-health-gate"
