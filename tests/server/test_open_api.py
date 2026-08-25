"""外部自动化评测 OpenAPI。"""

from __future__ import annotations

import time
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from server.models_db import (
    AttributionTask,
    AttributionTaskItem,
    Benchmark,
    CaseResultRow,
    EvalRun,
    JudgeModelConfig,
    TemporaryEvaluation,
)
from medeval.evaluation import EvaluationDimension
from medeval.models import (
    CaseEvaluation,
    CaseResult,
    DimensionCriteria,
    GuidelineItem,
    JudgeVerdict,
    Level,
    Source,
    TestCase,
    Turn,
)
from server.schemas import OpenTemporaryEvaluationCreate


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
            "deeptrace_execution_id": "agent-jenkins-354",
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
    assert completed.adapter_overrides["deeptrace"] == {"execution_id": "agent-jenkins-354"}
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


def test_open_api_read_permissions_can_query_all_platform_tasks(client, session):
    def create_key(name: str) -> tuple[int, dict[str, str]]:
        response = client.post(
            "/api/config/open-api-keys",
            json={
                "name": name,
                "permissions": ["evaluations:read", "attributions:read"],
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        return body["id"], {"X-MME-API-Key": body["api_key"]}

    first_key_id, first_headers = create_key("调用方 A")
    second_key_id, second_headers = create_key("调用方 B")
    first_run = EvalRun(
        run_slug="owner-a",
        name="调用方 A 任务",
        status="success",
        trigger_type="open_api",
        open_api_key_id=first_key_id,
    )
    second_run = EvalRun(
        run_slug="owner-b",
        name="调用方 B 任务",
        status="success",
        trigger_type="open_api",
        open_api_key_id=second_key_id,
    )
    session.add_all([first_run, second_run])
    session.flush()
    session.add_all(
        [
            AttributionTask(
                run_id=first_run.id,
                judge_model_id=1,
                status="success",
                requested_count=0,
                total_count=0,
            ),
            AttributionTask(
                run_id=second_run.id,
                judge_model_id=1,
                status="success",
                requested_count=0,
                total_count=0,
            ),
        ]
    )
    session.commit()

    first_list = client.get("/api/open/v1/evaluations", headers=first_headers).json()
    assert first_list["total"] == 2
    assert {item["id"] for item in first_list["items"]} == {first_run.id, second_run.id}
    assert client.get(
        f"/api/open/v1/evaluation-summaries/{second_run.id}",
        headers=first_headers,
    ).status_code == 200
    first_attributions = client.get(
        "/api/open/v1/attribution-tasks", headers=first_headers
    ).json()
    assert first_attributions["total"] == 2
    assert {item["run_id"] for item in first_attributions["items"]} == {
        first_run.id,
        second_run.id,
    }
    assert client.get("/api/open/v1/evaluations", headers=second_headers).json()["total"] == 2


def test_open_api_reports_config_backed_dashscope_model_as_available(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "server-only-key")
    headers = _open_headers(client, ["judge_models:read"])
    response = client.get("/api/open/v1/judge-models", headers=headers)
    assert response.status_code == 200
    default = next(
        item for item in response.json() if item["name"] == "百炼 DashScope · kimi-k2.6"
    )
    assert default["has_api_key"] is True


def test_open_api_temporary_evaluation_uses_supplied_context_and_case_contract(
    client, session, monkeypatch
):
    headers = _open_headers(client, ["temporary_evaluations:create"])
    benchmark = Benchmark(
        name="临时评测平台 Case",
        source="offline",
        storage_path="unused-in-test",
        case_count=1,
    )
    session.add(benchmark)
    session.commit()
    platform_case = TestCase(
        schema_version="2.1",
        sample_id="platform_case_01",
        scenario="化疗后发热",
        level=Level.L3,
        source=Source.offline,
        case_type="用药方法与药物安全",
        turns=[
            Turn(role="user", content=" 化疗后体温 38.5℃，\n我应该怎么办？ "),
            Turn(role="assistant", content="原平台 Case 回答，不应进入临时对话"),
        ],
        evaluation=CaseEvaluation(
            dimension_criteria={
                EvaluationDimension.professional_accuracy: DimensionCriteria(
                    criteria=["结合发热与中性粒细胞减少判断紧急程度"]
                )
            },
            guidelines=[
                GuidelineItem(
                    id="g01",
                    dimension=EvaluationDimension.professional_accuracy,
                    trigger="化疗后发热",
                    criteria=["明确建议尽快复查血常规"],
                    deduction_rule="缺失检查点时按未得分扣减",
                    max_score=2,
                )
            ],
        ),
    )

    from server.services import temporary_evaluation

    captured: dict = {}
    monkeypatch.setattr(
        temporary_evaluation,
        "_platform_benchmarks",
        lambda _session: [benchmark],
    )
    monkeypatch.setattr(
        temporary_evaluation.bm_domain,
        "load_benchmark_cases",
        lambda _candidate: [platform_case],
    )
    monkeypatch.setattr(temporary_evaluation, "build_judge_stack", lambda _config: [])

    async def fake_judge_all(case, trace, judges):
        captured["case"] = case
        captured["trace"] = trace
        captured["judges"] = judges
        verdicts = []
        for dimension in EvaluationDimension:
            score = 4.0 if dimension == EvaluationDimension.professional_accuracy else 5.0
            verdicts.append(
                JudgeVerdict(
                    name=f"dimension.{dimension.value}",
                    passed=score >= 3,
                    score=score,
                    max_score=5,
                    reason=(
                        "医学方向正确，但检查说明不完整"
                        if dimension == EvaluationDimension.professional_accuracy
                        else "满足该维度要求"
                    ),
                    evidence=["立即联系治疗团队并尽快急诊评估"],
                    details={
                        "satisfied_points": ["识别紧急处理需求"],
                        "issue_audits": (
                            [{"issue": "缺少复查项目"}]
                            if dimension == EvaluationDimension.professional_accuracy
                            else []
                        ),
                    },
                )
            )
        verdicts.append(
            JudgeVerdict(
                name="guideline.g01",
                passed=False,
                score=1,
                max_score=2,
                reason="未明确说明复查血常规",
                evidence=["尽快急诊评估"],
                details={
                    "applicable": True,
                    "missed_points": ["明确复查血常规"],
                    "checkpoint_audits": [{"checkpoint": "明确建议尽快复查血常规"}],
                },
            )
        )
        return CaseResult(
            case=case,
            trace=trace,
            verdicts=verdicts,
            medical_safety_passed=True,
        )

    monkeypatch.setattr(temporary_evaluation, "judge_all", fake_judge_all)

    response = client.post(
        "/api/open/v1/temporary-evaluations",
        headers=headers,
        json={
            "external_request_id": "external-chat-001",
            "question": "化疗后体温 38.5℃，我应该怎么办？",
            "answer": "请立即联系治疗团队并尽快急诊评估。",
            "user_profile": {"age": 52, "treatment_stage": "化疗后第 7 天"},
            "past_facts": [
                {
                    "occurred_at": "2026-08-18",
                    "label": "血常规",
                    "content": "中性粒细胞绝对值 0.8×10^9/L",
                }
            ],
            "rag_references": [
                {
                    "id": "rag-01",
                    "title": "处理原则",
                    "content": "化疗后发热伴中性粒细胞减少需紧急评估。",
                }
            ],
            "saved_contents": [
                {
                    "content_type": "medication",
                    "title": "当前用药",
                    "content": "昨日使用升白针。",
                }
            ],
        },
    )

    assert response.status_code == 202, response.text
    created = response.json()
    assert created["evaluation_id"].startswith("temporary_")
    assert created["external_request_id"] == "external-chat-001"
    assert created["status"] == "pending"
    assert created["status_url"].endswith(created["evaluation_id"])

    status_response = None
    for _ in range(100):
        status_response = client.get(created["status_url"], headers=headers)
        assert status_response.status_code == 200, status_response.text
        if status_response.json()["status"] in {"success", "failed"}:
            break
        time.sleep(0.01)
    assert status_response is not None
    status = status_response.json()
    assert status["status"] == "success", status
    assert status["error"] is None
    body = status["result"]
    assert body["evaluation_id"] == created["evaluation_id"]
    assert body["external_request_id"] == "external-chat-001"
    assert body["evaluation_mode"] == "single_turn"
    assert body["benchmark_case_matched"] is True
    assert body["case_source"] == {
        "benchmark_id": benchmark.id,
        "benchmark_name": "临时评测平台 Case",
        "sample_id": "platform_case_01",
        "scenario": "化疗后发热",
        "match_type": "normalized_exact_question",
    }
    assert body["total_score"] == 38
    assert body["grade"] == "优秀"
    assert body["passed"] is True
    assert len(body["dimensions"]) == 8
    professional = next(
        item for item in body["dimensions"]
        if item["dimension"] == "professional_accuracy"
    )
    assert professional["raw_score"] == 4
    assert professional["score"] == 3
    assert professional["base_deduction"] == 1
    assert professional["guideline_deduction"] == 1
    assert professional["deduction"] == 2
    assert professional["issue_audits"] == [{"issue": "缺少复查项目"}]
    assert body["guideline_results"][0]["deduction"] == 1
    assert body["guideline_results"][0]["missed_points"] == ["明确复查血常规"]
    assert any("未明确说明复查血常规" in item for item in body["deductions"])

    temporary_case = captured["case"]
    assert temporary_case.evaluation.dimension_criteria == platform_case.evaluation.dimension_criteria
    assert temporary_case.evaluation.guidelines == platform_case.evaluation.guidelines
    assert temporary_case.evaluation.assertions == []
    assert temporary_case.initial_state.user_profile["用户画像"]["age"] == 52
    context = temporary_case.initial_state.user_profile["临时评测辅助上下文"]
    assert context["RAG引用"][0]["id"] == "rag-01"
    assert context["病例夹"][0]["content_type"] == "medication"
    assert temporary_case.initial_state.timeline[0]["label"] == "血常规"
    assert [message.content for message in captured["trace"].messages] == [
        "化疗后体温 38.5℃，我应该怎么办？",
        "请立即联系治疗团队并尽快急诊评估。",
    ]
    assert "原平台 Case 回答" not in str(captured["trace"].messages)
    temporary_run = session.query(EvalRun).one()
    assert temporary_run.trigger_type == "open_api"
    assert temporary_run.name.endswith("临时评测")
    assert temporary_run.total == 1
    assert session.query(CaseResultRow).count() == 1
    assert session.query(CaseResultRow).one().run_id == temporary_run.id
    assert session.query(TemporaryEvaluation).count() == 1


def test_open_api_temporary_evaluation_requires_its_own_permission(client):
    headers = _open_headers(client, ["evaluations:create"])
    response = client.post(
        "/api/open/v1/temporary-evaluations",
        headers=headers,
        json={"question": "问题", "answer": "回答"},
    )
    assert response.status_code == 403


def test_open_api_temporary_evaluation_rejects_unknown_fields(client):
    headers = _open_headers(client, ["temporary_evaluations:create"])
    response = client.post(
        "/api/open/v1/temporary-evaluations",
        headers=headers,
        json={
            "question": "问题",
            "answer": "回答",
            "case_selector": {"benchmark_id": 1, "sample_id": "case_01"},
        },
    )
    assert response.status_code == 422


def test_open_api_temporary_evaluation_rejects_multi_turn_mode(client):
    headers = _open_headers(client, ["temporary_evaluations:create"])
    response = client.post(
        "/api/open/v1/temporary-evaluations",
        headers=headers,
        json={
            "evaluation_mode": "multi_turn",
            "question": "问题",
            "answer": "回答",
        },
    )
    assert response.status_code == 422
    assert "single_turn" in response.json()["detail"]


def test_open_api_temporary_evaluation_rejects_unknown_judge_model(client):
    headers = _open_headers(client, ["temporary_evaluations:create"])
    response = client.post(
        "/api/open/v1/temporary-evaluations",
        headers=headers,
        json={"question": "问题", "answer": "回答", "judge_model_id": 999999},
    )
    assert response.status_code == 404
    assert "判分模型 999999 不存在" in response.json()["detail"]


def test_temporary_evaluation_uses_generic_contract_when_question_does_not_match(
    session, monkeypatch
):
    benchmark = Benchmark(
        name="自动匹配未命中测试集",
        source="offline",
        storage_path="unused-no-match",
        case_count=1,
    )
    session.add(benchmark)
    session.commit()
    platform_case = TestCase(
        schema_version="2.1",
        sample_id="other_case",
        scenario="其他问题",
        level=Level.L2,
        source=Source.offline,
        turns=[Turn(role="user", content="这是另一个问题")],
        evaluation=CaseEvaluation(
            dimension_criteria={
                EvaluationDimension.communication: DimensionCriteria(
                    criteria=["使用简洁表达"]
                )
            }
        ),
    )
    from server.services import temporary_evaluation

    monkeypatch.setattr(
        temporary_evaluation,
        "_platform_benchmarks",
        lambda _session: [benchmark],
    )
    monkeypatch.setattr(
        temporary_evaluation.bm_domain,
        "load_benchmark_cases",
        lambda _benchmark: [platform_case],
    )
    payload = OpenTemporaryEvaluationCreate(question="没有命中的问题", answer="回答")

    temporary_case, case_source = temporary_evaluation._temporary_case(
        session, payload, "temporary_no_match"
    )

    assert case_source is None
    assert temporary_case.evaluation.dimension_criteria == {}
    assert temporary_case.evaluation.guidelines == []


def test_temporary_evaluation_rejects_ambiguous_question_contracts(
    session, monkeypatch
):
    first_benchmark = Benchmark(
        name="重复问题测试集一",
        source="offline",
        storage_path="unused-ambiguous-a",
        case_count=1,
    )
    second_benchmark = Benchmark(
        name="重复问题测试集二",
        source="offline",
        storage_path="unused-ambiguous-b",
        case_count=1,
    )
    session.add_all([first_benchmark, second_benchmark])
    session.commit()

    def build_case(sample_id: str, criterion: str) -> TestCase:
        return TestCase(
            schema_version="2.1",
            sample_id=sample_id,
            scenario="重复问题",
            level=Level.L2,
            source=Source.offline,
            turns=[Turn(role="user", content="同一个问题")],
            evaluation=CaseEvaluation(
                dimension_criteria={
                    EvaluationDimension.communication: DimensionCriteria(
                        criteria=[criterion]
                    )
                }
            ),
        )

    cases = {
        first_benchmark.id: [build_case("case_a", "标准一")],
        second_benchmark.id: [build_case("case_b", "标准二")],
    }
    from server.services import temporary_evaluation

    monkeypatch.setattr(
        temporary_evaluation,
        "_platform_benchmarks",
        lambda _session: [first_benchmark, second_benchmark],
    )
    monkeypatch.setattr(
        temporary_evaluation.bm_domain,
        "load_benchmark_cases",
        lambda benchmark: cases[benchmark.id],
    )

    with pytest.raises(HTTPException) as exc_info:
        temporary_evaluation._match_platform_case(session, " 同一个\n问题 ")

    assert exc_info.value.status_code == 409
    assert "评分契约不同" in str(exc_info.value.detail)


def test_temporary_evaluation_does_not_apply_multi_turn_case_contract(
    session, monkeypatch
):
    benchmark = Benchmark(
        name="多轮问题测试集",
        source="offline",
        storage_path="unused-multi-turn",
        case_count=1,
    )
    session.add(benchmark)
    session.commit()
    multi_turn_case = TestCase(
        schema_version="2.1",
        sample_id="multi_turn_case",
        scenario="多轮问题",
        level=Level.L2,
        source=Source.offline,
        turns=[
            Turn(role="user", content="同一个开场问题"),
            Turn(role="assistant", content="请补充信息"),
            Turn(role="user", content="这是第二个用户回合"),
        ],
        evaluation=CaseEvaluation(
            dimension_criteria={
                EvaluationDimension.clinical_inquiry: DimensionCriteria(
                    criteria=["覆盖多轮追问"]
                )
            }
        ),
    )
    from server.services import temporary_evaluation

    monkeypatch.setattr(
        temporary_evaluation,
        "_platform_benchmarks",
        lambda _session: [benchmark],
    )
    monkeypatch.setattr(
        temporary_evaluation.bm_domain,
        "load_benchmark_cases",
        lambda _benchmark: [multi_turn_case],
    )

    with pytest.raises(HTTPException) as exc_info:
        temporary_evaluation._match_platform_case(session, "同一个开场问题")

    assert exc_info.value.status_code == 422
    assert "目前仅支持单轮模式" in str(exc_info.value.detail)


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
            detail_json={
                "case": {
                    "schema_version": "2.0",
                    "sample_id": "case_1",
                    "scenario": "潮热用药",
                    "case_type": "用药安全",
                    "level": "L2",
                    "initial_state": {
                        "user_profile": {
                            "年龄": 45,
                            "肿瘤状态": "HER2 3+、ER 弱阳性",
                        },
                        "timeline": [
                            {"日期": "2026-08-01", "事件": "开始服用内分泌药物"}
                        ],
                        "long_term_memories": ["曾因潮热影响夜间睡眠"],
                    },
                },
                "trace": {
                    "messages": [
                        {"role": "user", "content": "最近潮热很明显，怎么办？"},
                        {
                            "role": "assistant",
                            "content": "先记录频次，并联系医生评估当前用药。",
                        },
                    ],
                    "duration_ms": 1234,
                    "evaluation_identity": {
                        "login_account": "+8610000000101",
                        "fixed_verification_code": "731904",
                        "test_user_id": "secret-user-id",
                    },
                    "cx_literature_audit_fetched": True,
                    "cx_literature_audits": [
                        {
                            "id": "audit-1",
                            "query": "乳腺癌 内分泌治疗 潮热",
                            "mode": "general",
                            "rawHitCount": 25,
                            "scorePassedCount": 8,
                            "candidateSourceCount": 5,
                            "selectedSourceCount": 1,
                            "scoreThreshold": 0.65,
                            "hits": [
                                {
                                    "rank": 1,
                                    "passedScore": True,
                                    "selected": True,
                                    "raw": {
                                        "title": "乳腺癌内分泌治疗相关症状管理指南",
                                        "score": 0.92,
                                        "content": "应结合症状频次和严重程度选择处理方式。",
                                    },
                                }
                            ],
                        }
                    ],
                    "agent_chain": {
                        "status": "synced",
                        "summary": {
                            "steps": [
                                {
                                    "title": "Agent 接收请求",
                                    "type": "AGENT",
                                    "duration_ms": 1234,
                                },
                                {
                                    "title": "医学文献 RAG",
                                    "type": "TOOL",
                                    "duration_ms": 260,
                                },
                            ],
                            "sources": [
                                {
                                    "key": "literature_rag",
                                    "label": "医学文献 RAG",
                                    "status": "hit",
                                    "calls": 1,
                                    "count": 1,
                                }
                            ],
                            "quality": {
                                "model_calls": 1,
                                "tool_calls": 1,
                                "total_tokens": 1200,
                            },
                            "risks": [],
                            "actions": [],
                        },
                    },
                },
                "verdicts": [
                    {
                        "name": f"dimension.{dimension}",
                        "passed": True,
                        "score": 5,
                        "max_score": 5,
                        "reason": f"{dimension} 维度判定理由",
                        "evidence": ["回答中的对应证据"],
                    }
                    for dimension in (
                        "medical_safety",
                        "professional_accuracy",
                        "clinical_inquiry",
                        "personalization",
                        "plan_feasibility",
                        "empathy",
                        "executability",
                        "communication",
                    )
                ],
                "medical_safety_passed": True,
                "release_passed": True,
                "judge_error": False,
                "dimension_raw_scores": {
                    "medical_safety": 5,
                    "professional_accuracy": 5,
                    "clinical_inquiry": 5,
                    "personalization": 5,
                    "plan_feasibility": 5,
                    "empathy": 5,
                    "executability": 5,
                    "communication": 5,
                },
                "dimension_scores": {
                    "medical_safety": 5,
                    "professional_accuracy": 4,
                    "clinical_inquiry": 5,
                    "personalization": 5,
                    "plan_feasibility": 5,
                    "empathy": 5,
                    "executability": 5,
                    "communication": 5,
                },
                "dimension_max": {
                    "medical_safety": 5,
                    "professional_accuracy": 5,
                    "clinical_inquiry": 5,
                    "personalization": 5,
                    "plan_feasibility": 5,
                    "empathy": 5,
                    "executability": 5,
                    "communication": 5,
                },
                "guideline_scores": [
                    {
                        "id": "g01",
                        "dimension": "professional_accuracy",
                        "criterion": "说明潮热处理需结合频次和严重程度",
                        "checkpoints": ["询问潮热频次", "询问是否影响睡眠"],
                        "deduction_rule": "每缺少一个检查点扣 1 分，最多扣 2 分",
                        "applicable": True,
                        "score": 1,
                        "max_score": 2,
                        "deduction": 1,
                        "missed_points": ["未询问是否影响睡眠"],
                        "reason": "只覆盖了频次记录",
                        "evidence": ["先记录频次"],
                    }
                ],
                "composite_score": 44,
                "grade": "优秀",
                "score_deductions": [
                    "professional_accuracy 指南 g01 -1分：只覆盖了频次记录"
                ],
                "stability": "stable_pass",
            },
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
                            "evidence_summary": "RAG 已召回药物禁忌信息，但最终回答没有使用。",
                            "observed_gap": {
                                "direct_evidence": ["最终回答未提及已召回的禁忌条件"],
                                "gap": "关键禁忌信息没有进入最终建议。",
                            },
                            "impact": "用户可能无法获得与当前用药相关的安全提醒。",
                                "primary_cause": {
                                    "code": "rag_not_grounded",
                                    "label": "召回证据未用于回答",
                                    "owner": "generator",
                                },
                                "optimization_classification": {
                                    "category_primary": "RAG 优化",
                                    "category_secondary": "已召回但未使用",
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
                        {
                            "deduction_id": "guideline.g03",
                            "dimension": "professional_accuracy",
                            "deduction_validation": "insufficient_evidence",
                            "evaluation_issue_category": "missing_rag_reference",
                            "severity": "medium",
                            "issue_type": "missing_citation",
                            "root_cause_stage": "rag",
                            "finding": "医学结论缺少可回链的 RAG 原文",
                            "primary_cause": {
                                "code": "missing_rag_reference",
                                "label": "RAG 引用未绑定到回答",
                                "owner": "rag",
                            },
                            "recommendations": [
                                {
                                    "priority": "P1",
                                    "target": "引用绑定",
                                    "action": "将选中文献与回答结论建立可回链绑定",
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
    assert len(output["cx_agent_optimization_summary"]["clusters"]) == 2
    case = output["cases"][0]
    assert case["case_report_url"] == (
        f"{settings.frontend_url}/runs/{run.id}/attribution-tasks/{task.id}/cases/case_1"
    )
    assert case["case_evaluation_url"] == (
        f"{settings.frontend_url}/runs/{run.id}/cases/case_1"
    )
    evaluation_markdown = case["evaluation_markdown"]
    assert "# 原评测明细 · case_1" in evaluation_markdown
    assert "## 对话明细" in evaluation_markdown
    assert "最近潮热很明显，怎么办？" in evaluation_markdown
    assert "## 用户画像" in evaluation_markdown
    assert "HER2 3+、ER 弱阳性" in evaluation_markdown
    assert "## Timeline 与过往事实" in evaluation_markdown
    assert "开始服用内分泌药物" in evaluation_markdown
    assert "## Agent 调用链" in evaluation_markdown
    assert "Agent 接收请求" in evaluation_markdown
    assert "## 医学文献 RAG" in evaluation_markdown
    assert "乳腺癌内分泌治疗相关症状管理指南" in evaluation_markdown
    assert "## 八维评分" in evaluation_markdown
    assert "专业准确性与边界 | 5/5 | -1 | 4/5" in evaluation_markdown
    assert "## 指南评分与扣分逻辑" in evaluation_markdown
    assert "每缺少一个检查点扣 1 分" in evaluation_markdown
    assert "+8610000000101" not in evaluation_markdown
    assert "731904" not in evaluation_markdown
    assert "secret-user-id" not in evaluation_markdown
    deductions = case["cx_agent_optimization"]["deductions"]
    assert len(deductions) == 2
    assert deductions[0]["deduction_id"] == "guideline.g01"
    assert deductions[0]["optimization_classification"] == {
        "category_primary": "RAG 优化",
        "category_secondary": "已召回但未使用",
        "domain": "medical_rag",
        "component": "rag_grounding",
        "failure_mode": "rag_not_grounded",
        "action_type": "grounding_rule",
        "evidence_status": "sufficient",
        "coverage_status": "mapped",
    }
    assert deductions[0]["recommendations"][0]["scope"] == "cx_agent"
    assert deductions[1]["deduction_id"] == "guideline.g03"
    assert deductions[1]["optimization_classification"]["component"] == "citation_binding"
    assert case["cx_agent_optimization"]["recommendations"][0]["target"] == "回答生成"
    markdown = case["cx_agent_optimization"]["markdown"]
    assert "# CX-Agent 归因结论与优化建议" in markdown
    assert "已召回证据但回答没有引用" in markdown
    assert "生成前逐条核对选中文献" in markdown
    assert "医学结论缺少可回链的 RAG 原文" in markdown
    assert "## 02 专业准确性与边界" in markdown
    assert "### P1 · 较高优先级" in markdown
    assert "#### 问题分类：RAG 优化 / 已召回但未使用" in markdown
    assert "- 直接证据：" in markdown
    assert "- 导致问题：用户可能无法获得与当前用药相关的安全提醒。" in markdown
    assert "判分模型" not in markdown
    assert "Benchmark 判据" not in markdown
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
