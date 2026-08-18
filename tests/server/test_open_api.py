"""外部自动化评测 OpenAPI。"""

from __future__ import annotations

from types import SimpleNamespace

from server.models_db import (
    AttributionTask,
    AttributionTaskItem,
    Benchmark,
    CaseResultRow,
    EvalRun,
    JudgeModelConfig,
)


def _open_headers(client, permissions: list[str] | None = None) -> dict[str, str]:
    response = client.post(
        "/api/config/open-api-keys",
        json={
            "name": "OpenAPI 测试 Key",
            "permissions": permissions
            or [
                "benchmarks:read",
                "judge_models:read",
                "evaluations:create",
                "evaluations:read",
            ],
        },
    )
    assert response.status_code == 201, response.text
    return {"X-MME-API-Key": response.json()["api_key"]}


def test_open_api_is_disabled_without_key(client):
    response = client.get("/api/open/v1/benchmarks")
    assert response.status_code == 503
    assert "尚未启用" in response.json()["detail"]


def test_open_api_lists_resources_and_creates_evaluation(
    client, session, monkeypatch, settings
):
    open_headers = _open_headers(client)
    benchmark = Benchmark(
        name="开放接口测试集",
        description="用于 OpenAPI 测试",
        source="offline",
        case_count=3,
        levels=["L2", "L3"],
    )
    judge_model = JudgeModelConfig(
        name="开放接口判分模型",
        provider="openai",
        model="judge-test-model",
        api_key="judge-secret",
    )
    session.add_all([benchmark, judge_model])
    session.commit()

    from server.routers import open_api

    captured: dict = {}

    async def submit(run_id, _job):
        captured["run_id"] = run_id

    def fake_build(*args, **kwargs):
        captured.update(kwargs)

        async def noop(_progress):
            return None

        return noop

    monkeypatch.setattr(open_api, "build_eval_job", fake_build)
    monkeypatch.setattr(
        open_api,
        "get_job_runner",
        lambda: SimpleNamespace(
            submit=submit,
            progress_snapshot=lambda _run_id: None,
            queue_snapshot=lambda _run_id: {"state": "queued", "position": 1},
        ),
    )

    benchmarks = client.get("/api/open/v1/benchmarks", headers=open_headers)
    assert benchmarks.status_code == 200
    assert any(item["id"] == benchmark.id for item in benchmarks.json())

    models = client.get("/api/open/v1/judge-models", headers=open_headers)
    assert models.status_code == 200
    model = next(item for item in models.json() if item["id"] == judge_model.id)
    assert model == {
        "id": judge_model.id,
        "name": "开放接口判分模型",
        "provider": "openai",
        "model": "judge-test-model",
        "has_api_key": True,
    }

    response = client.post(
        "/api/open/v1/evaluations",
        headers=open_headers,
        json={
            "benchmark_id": benchmark.id,
            "name": "OpenAPI 自动化评测",
            "evaluation_mode": "multi_turn",
            "enable_rag": True,
            "repeat": 3,
            "levels": ["L2"],
            "enable_judge": True,
            "judge_model_id": judge_model.id,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["result"] is None
    assert body["dashboard_url"] == f"{settings.frontend_url}/runs/{body['id']}"
    assert body["evaluation_mode"] == "multi_turn"
    assert body["repeat"] == 3
    assert body["enable_rag"] is True
    assert body["enable_judge"] is True
    assert body["judge_model_id"] == judge_model.id
    assert body["queue_position"] == 1
    assert captured["run_id"] == body["id"]
    assert captured["levels"] == ["L2"]
    assert captured["repeat"] == 3
    assert captured["adapter_full"]["enable_rag"] is True
    assert captured["adapter_full"]["evaluation_mode"] == "multi_turn"
    assert captured["judge_full"]["enabled"] is True
    assert captured["judge_full"]["model"] == "judge-test-model"
    assert captured["judge_full"]["api_key"] == "judge-secret"

    status = client.get(
        f"/api/open/v1/evaluation-summaries/{body['id']}", headers=open_headers
    )
    assert status.status_code == 200
    assert status.json()["judge_model_id"] == judge_model.id
    assert status.json()["dashboard_url"] == f"{settings.frontend_url}/runs/{body['id']}"
    assert status.json()["result"] is None

    completed = session.get(EvalRun, body["id"])
    assert completed is not None
    completed.status = "success"
    completed.total = 63
    completed.passed = 48
    completed.pass_rate = 48 / 63
    session.commit()

    completed_status = client.get(
        f"/api/open/v1/evaluation-summaries/{body['id']}", headers=open_headers
    )
    assert completed_status.status_code == 200
    assert completed_status.json()["result"] == {
        "total_cases": 63,
        "passed_cases": 48,
        "failed_cases": 15,
        "pass_rate": 48 / 63,
    }


def test_open_api_rejects_model_when_judge_is_disabled(client, session):
    open_headers = _open_headers(client, ["evaluations:create"])
    benchmark = Benchmark(name="无判分测试集", source="offline")
    session.add(benchmark)
    session.commit()

    response = client.post(
        "/api/open/v1/evaluations",
        headers=open_headers,
        json={
            "benchmark_id": benchmark.id,
            "name": "不应创建",
            "enable_judge": False,
            "judge_model_id": 1,
        },
    )
    assert response.status_code == 422
    assert "不能传 judge_model_id" in response.text


def test_open_api_lists_results_by_trigger_type_with_dashboard_links(client, session, settings):
    headers = _open_headers(client, ["evaluations:read"])
    scheduled = EvalRun(
        run_slug="scheduled-result",
        name="定时回归",
        status="success",
        trigger_type="scheduled",
        total=5,
        passed=3,
        pass_rate=0.6,
    )
    pending = EvalRun(
        run_slug="scheduled-pending",
        name="定时等待中",
        status="pending",
        trigger_type="scheduled",
    )
    manual = EvalRun(
        run_slug="manual-result",
        name="人工评测",
        status="success",
        trigger_type="manual",
    )
    session.add_all([scheduled, pending, manual])
    session.flush()
    session.add_all(
        [
            CaseResultRow(run_id=scheduled.id, sample_id="c1", grade="优秀"),
            CaseResultRow(run_id=scheduled.id, sample_id="c2", grade="良好"),
            CaseResultRow(run_id=scheduled.id, sample_id="c3", grade="合格"),
            CaseResultRow(run_id=scheduled.id, sample_id="c4", grade="不合格"),
            CaseResultRow(run_id=scheduled.id, sample_id="c5", grade=""),
        ]
    )
    session.commit()

    response = client.get(
        "/api/open/v1/evaluations?trigger_type=scheduled",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    finished = next(item for item in body["items"] if item["id"] == scheduled.id)
    assert finished["dashboard_url"] == f"{settings.frontend_url}/runs/{scheduled.id}"
    assert finished["result"] == {
        "total_cases": 5,
        "passed_cases": 3,
        "failed_cases": 2,
        "pass_rate": 0.6,
        "excellent_cases": 1,
        "good_cases": 1,
        "qualified_cases": 1,
        "unqualified_cases": 1,
        "other_cases": 1,
    }
    waiting = next(item for item in body["items"] if item["id"] == pending.id)
    assert waiting["result"] is None
    assert all(item["trigger_type"] == "scheduled" for item in body["items"])


def test_open_api_rejects_invalid_key(client):
    _open_headers(client, ["benchmarks:read"])
    response = client.get("/api/open/v1/benchmarks", headers={"X-MME-API-Key": "wrong"})
    assert response.status_code == 403


def test_open_api_reports_config_backed_dashscope_model_as_available(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "server-only-key")
    headers = _open_headers(client, ["judge_models:read"])
    response = client.get("/api/open/v1/judge-models", headers=headers)
    assert response.status_code == 200
    default = next(
        item for item in response.json() if item["name"] == "百炼 DashScope · kimi-k2.6"
    )
    assert default["has_api_key"] is True


def test_open_api_returns_run_overview_metrics_without_case_data(client, session):
    headers = _open_headers(client, ["evaluations:read"])
    run = EvalRun(
        run_slug="open-run-overview",
        name="OpenAPI 总览",
        status="success",
        total=63,
        passed=13,
        pass_rate=13 / 63,
        medical_safety_failed=35,
        grading={
            "avg_composite": 11.706,
            "avg_dimension": {"medical_safety": 2.2},
            "reliability": {"k": 3, "pass_at_k": 0.396},
        },
        stability_distribution={"stable_pass": 8, "flaky": 17, "stable_fail": 38},
        latency_summary={"count": 189, "avg_ms": 41454},
        ttft_summary={"avg_ms": 9206},
        token_summary={"total_tokens": 24889002, "avg_tokens_per_run": 131687},
        pass_rate_ci={"lower": 0.11, "upper": 0.302},
        failure_tag_counter={"medical_safety_risk": 35},
        by_level={"L2": {"total": 63, "passed": 13}},
        by_scenario={"报告解读": {"total": 11, "passed": 2}},
        by_case_type={"医学诊疗": {"total": 63, "passed": 13}},
    )
    session.add(run)
    session.commit()

    response = client.get(
        f"/api/open/v1/evaluation-summaries/{run.id}", headers=headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == run.id
    assert body["result"] == {
        "total_cases": 63,
        "passed_cases": 13,
        "failed_cases": 50,
        "pass_rate": 13 / 63,
    }
    assert body["avg_composite"] == 11.706
    assert body["avg_dimension"] == {"medical_safety": 2.2}
    assert body["stability_distribution"] == {"stable_pass": 8, "flaky": 17, "stable_fail": 38}
    assert body["latency_summary"] == {"count": 189, "avg_ms": 41454}
    assert body["ttft_summary"] == {"avg_ms": 9206}
    assert body["token_summary"]["total_tokens"] == 24889002
    assert body["reliability"] == {"k": 3, "pass_at_k": 0.396}
    assert body["by_scenario"]["报告解读"] == {"total": 11, "passed": 2}
    assert "cases" not in body


def test_open_api_returns_only_cx_agent_attribution_optimizations(client, session, settings):
    headers = _open_headers(client, ["attributions:read"])
    run = EvalRun(run_slug="attribution-open-api", name="归因 OpenAPI 测试", status="success")
    session.add(run)
    session.flush()
    task = AttributionTask(
        run_id=run.id,
        judge_model_id=7,
        judge_model_name="归因模型",
        status="success",
        requested_count=1,
        total_count=1,
        completed_count=1,
        success_count=1,
    )
    session.add(task)
    session.flush()
    session.add(
        CaseResultRow(
            run_id=run.id,
            sample_id="case_1",
            scenario="潮热用药",
            case_type="用药安全",
        )
    )
    session.add(
        AttributionTaskItem(
            task_id=task.id,
            sample_id="case_1",
            status="success",
            analysis_json={
                "available": True,
                "analysis": {
                    "overall": {"summary": "回答没有使用已召回的药物禁忌证据"},
                    "deduction_analyses": [
                        {
                            "deduction_id": "guideline.g01",
                            "dimension": "professional_accuracy",
                            "deduction_validation": "supported",
                            "severity": "high",
                            "issue_type": "factual_error",
                            "root_cause_stage": "generation",
                            "finding": "已召回证据但回答没有引用",
                            "primary_cause": {
                                "code": "rag_not_grounded",
                                "label": "召回证据未用于回答",
                                "owner": "generator",
                            },
                            "recommendations": [
                                {
                                    "priority": "P1",
                                    "target": "提示词优化",
                                    "action": "生成前逐条核对选中文献",
                                }
                            ],
                        },
                        {
                            "deduction_id": "guideline.g02",
                            "dimension": "medical_safety",
                            "deduction_validation": "questionable",
                            "finding": "判分模型忽略了回答后半段",
                            "primary_cause": {
                                "code": "judge_logic_issue",
                                "label": "判分需复核",
                                "owner": "judge",
                            },
                            "recommendations": [
                                {
                                    "priority": "P0",
                                    "target": "判分模型",
                                    "action": "修正判分上下文读取",
                                }
                            ],
                        },
                    ],
                    "global_recommendations": [
                        {
                            "priority": "P1",
                            "target": "回答生成",
                            "action": "增加文献覆盖检查",
                        },
                        {
                            "priority": "P0",
                            "target": "Benchmark 判据",
                            "action": "修正冲突规则",
                        },
                    ],
                },
            },
        )
    )
    session.commit()

    response = client.get("/api/open/v1/attribution-tasks", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    output = body["items"][0]
    assert output["id"] == task.id
    assert output["report_url"] == (
        f"{settings.frontend_url}/runs/{run.id}/attribution-tasks/{task.id}"
    )
    assert output["cx_agent_optimization_summary"]["cx_agent_case_count"] == 1
    assert len(output["cx_agent_optimization_summary"]["clusters"]) == 1
    case = output["cases"][0]
    deductions = case["cx_agent_optimization"]["deductions"]
    assert len(deductions) == 1
    assert deductions[0]["deduction_id"] == "guideline.g01"
    assert deductions[0]["optimization_classification"] == {
        "domain": "medical_rag",
        "component": "rag_grounding",
        "failure_mode": "rag_not_grounded",
        "action_type": "grounding_rule",
        "evidence_status": "sufficient",
        "coverage_status": "mapped",
    }
    assert deductions[0]["recommendations"][0]["scope"] == "cx_agent"
    assert case["cx_agent_optimization"]["recommendations"][0]["target"] == "回答生成"
    assert "判分模型" not in str(body)
    assert "Benchmark 判据" not in str(body)

    other_key = client.post(
        "/api/config/open-api-keys",
        json={"name": "仅评测查询测试 Key", "permissions": ["evaluations:read"]},
    )
    assert other_key.status_code == 201, other_key.text
    forbidden = client.get(
        "/api/open/v1/attribution-tasks",
        headers={"X-MME-API-Key": other_key.json()["api_key"]},
    )
    assert forbidden.status_code == 403
