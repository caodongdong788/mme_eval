from __future__ import annotations

from types import SimpleNamespace

from factories import make_report

from server.db import session_scope
from server.ingest import ingest_report
from server.models_db import Benchmark, CaseResultRow
from server.services.case_attribution import _configure_attribution_model, _safe_provider_error


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
    async def chat_json(self, model, prompt, temperature, max_retries=0):
        assert model == "fake-model"
        assert "rag_audits" in prompt
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


def test_kimi_k3_attribution_forces_supported_thinking_parameters():
    judge = SimpleNamespace(model="kimi/kimi-k3", temperature=0.0, enable_thinking=False)

    temperature = _configure_attribution_model(judge)

    assert temperature == 0.6
    assert judge.enable_thinking is True


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

    response = client.post(f"/api/runs/{run_id}/cases/bc_002/attribution")
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["stale"] is False
    assert payload["analysis"]["overall"]["primary_cause_code"] == "reasoning_error"
    refs = payload["analysis"]["deduction_analyses"][0]["causal_chain"][0]["evidence_refs"]
    assert refs == ["dimension.professional_accuracy"]
    assert payload["metadata"]["prompt_version"] == "case-attribution-v2"

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
    response = client.post(f"/api/runs/{run_id}/cases/bc_001/attribution")
    assert response.status_code == 422
    assert response.json()["detail"] == "归因分析仅面向不合格用例"
