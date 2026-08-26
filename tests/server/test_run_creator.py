import asyncio
from types import SimpleNamespace

import server.routers.runs as runs_router
from server.routers.runs import crud
from server.models_db import AttributionTask, AttributionTaskItem, Benchmark, EvalRun
from server.schemas import RunCreate, RunSummaryOut
from server.services.attribution_tasks import refresh_run_attribution_summary
from server.services.runs import create_derived_run, list_runs, prepare_create_run


def test_create_route_passes_logged_in_creator(monkeypatch):
    captured = {}
    run = EvalRun(id=7, run_slug="(pending)", name="creator-run", status="pending")
    plan = SimpleNamespace(
        run=run,
        benchmark_id=1,
        run_name="creator-run",
        levels=[],
        limit=0,
        repeat=1,
        judge_full=None,
        adapter_full={},
    )

    def fake_prepare(_session, _payload, *, created_by=None):
        captured["created_by"] = created_by
        return plan

    class FakeJobRunner:
        async def submit(self, run_id, _job):
            captured["run_id"] = run_id

    monkeypatch.setattr(crud.runs_svc, "prepare_create_run", fake_prepare)
    monkeypatch.setattr(runs_router, "build_eval_job", lambda *args, **kwargs: object())
    monkeypatch.setattr(crud, "get_job_runner", lambda: FakeJobRunner())

    result = asyncio.run(
        crud.create_run(
            RunCreate(benchmark_id=1),
            session=object(),
            current_user=SimpleNamespace(name="曹冬东"),
        )
    )

    assert result is run
    assert captured == {"created_by": "曹冬东", "run_id": 7}


def test_prepare_create_run_stores_logged_in_creator(session):
    benchmark = Benchmark(name="creator-benchmark", source="offline")
    session.add(benchmark)
    session.flush()

    plan = prepare_create_run(
        session,
        RunCreate(benchmark_id=benchmark.id, run_name="creator-run"),
        created_by="曹冬东",
    )

    assert plan.run.created_by == "曹冬东"
    assert RunSummaryOut.model_validate(plan.run).created_by == "曹冬东"


def test_run_summary_exposes_average_composite_score(session):
    run = EvalRun(
        run_slug="score-summary",
        name="score-summary",
        status="success",
        grading={"avg_composite": 31.25},
    )
    session.add(run)
    session.flush()

    assert RunSummaryOut.model_validate(run).avg_composite == 31.25


def test_run_list_exposes_deduplicated_cx_agent_optimization_count(session):
    benchmark = Benchmark(name="真实患者 Benchmark", source="offline")
    session.add(benchmark)
    session.flush()
    run = EvalRun(
        run_slug="attribution-summary",
        name="归因汇总",
        status="success",
        benchmark_id=benchmark.id,
    )
    without_attribution = EvalRun(run_slug="without-attribution", status="success")
    session.add_all([run, without_attribution])
    session.flush()

    task = AttributionTask(run_id=run.id, judge_model_id=1, status="success")
    session.add(task)
    session.flush()
    snapshot = {
        "available": True,
        "analysis": {
            "score_health": {"status": "healthy"},
            "deduction_analyses": [
                {
                    "deduction_id": "guideline.medical_safety",
                    "dimension": "medical_safety",
                    "severity": "high",
                    "deduction_validation": "supported",
                    "primary_cause": {
                        "code": "safety_policy_error",
                        "label": "安全策略遗漏",
                        "owner": "safety_policy",
                    },
                    "optimization_classification": {
                        "category_primary": "输出校验与安全守卫",
                        "category_secondary": "遗漏风险提示",
                        "domain": "medical_safety",
                        "component": "safety_policy",
                        "failure_mode": "safety_policy_error",
                        "action_type": "safety_rule",
                    },
                    "recommendations": [
                        {"scope": "cx_agent", "priority": "P0", "target": "安全策略", "action": "补齐风险提示"}
                    ],
                }
            ],
        },
    }
    session.add_all([
        AttributionTaskItem(task_id=task.id, sample_id="case_1", status="success", analysis_json=snapshot),
        AttributionTaskItem(task_id=task.id, sample_id="case_2", status="success", analysis_json=snapshot),
    ])
    session.flush()
    refresh_run_attribution_summary(session, run.id)

    listed = {item.id: item for item in list_runs(session)}

    assert listed[run.id].cx_agent_optimization_count == 1
    assert listed[run.id].cx_agent_p0_optimization_count == 1
    assert listed[run.id].benchmark_name == "真实患者 Benchmark"
    assert listed[without_attribution.id].cx_agent_optimization_count is None
    assert listed[without_attribution.id].cx_agent_p0_optimization_count is None
    summary = RunSummaryOut.model_validate(listed[run.id])
    assert summary.cx_agent_optimization_count == 1
    assert summary.cx_agent_p0_optimization_count == 1
    assert summary.benchmark_name == "真实患者 Benchmark"


def test_derived_run_stores_initiating_creator(session):
    source = EvalRun(run_slug="source", name="源评测", status="success")
    session.add(source)
    session.flush()

    derived = create_derived_run(
        session,
        source,
        suffix="重判",
        created_by="评测发起人",
    )

    assert derived.created_by == "评测发起人"
