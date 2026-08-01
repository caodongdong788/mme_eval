import asyncio
from types import SimpleNamespace

import server.routers.runs as runs_router
from server.routers.runs import crud
from server.models_db import Benchmark, EvalRun
from server.schemas import RunCreate, RunSummaryOut
from server.services.runs import create_derived_run, prepare_create_run


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
