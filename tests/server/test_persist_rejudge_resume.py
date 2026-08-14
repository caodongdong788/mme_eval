"""平台完整补齐：落 trace + has_traces、离线重判、断点续跑、置顶、附加列迁移。"""

from __future__ import annotations

import asyncio

from factories import make_report
from medeval import trace_store
from server.db import session_scope
from server.eval_job import build_eval_job, build_rejudge_job, build_resume_job, build_retry_case_job
from server.ingest import finalize_run, ingest_report
from server.models_db import Benchmark, CaseResultRow, EvalRun
from server.progress import InMemoryProgress
from server.services.eval_artifacts import IncrementalRunPersister


# ---------------------------------------------------------------------------
# 辅助：在磁盘 + DB 造一个"源 run"（含 report.json 与可选 traces.jsonl.gz）


def _seed_source_run(settings, *, with_traces: bool = True, n_runs: int = 1) -> int:
    report = make_report("src_2026-06-04_1")
    report.n_runs = n_runs
    slug = report.run_name
    out_dir = settings.outputs_dir / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(report.model_dump_json(), encoding="utf-8")

    if with_traces:
        cases = [r.case for r in report.results]
        per_case_traces = [[r.trace] for r in report.results]
        trace_store.write_traces(
            out_dir,
            cases,
            per_case_traces,
            store_raw="on_error",
            meta={
                "schema": trace_store.SCHEMA_VERSION,
                "adapter_fingerprint": "fp-src",
                "store_raw": "on_error",
                "n_runs": n_runs,
                "n_cases": len(cases),
            },
        )

    with session_scope() as s:
        bm = Benchmark(name="src-bm", source="uploaded", storage_path="/tmp/none")
        s.add(bm)
        s.flush()
        row = EvalRun(
            run_slug=slug,
            name="源评测",
            status="success",
            benchmark_id=bm.id,
            n_runs=n_runs,
            has_traces=with_traces,
        )
        s.add(row)
        s.flush()
        return row.id


# ---------------------------------------------------------------------------
# 平台正常评测：落 trace + has_traces + retention 收尾


def test_eval_job_persists_traces_and_runs_retention(
    initialized_db, settings, monkeypatch
):
    with session_scope() as s:
        bm = Benchmark(name="x", source="uploaded", storage_path="/tmp/none")
        s.add(bm)
        s.flush()
        run = EvalRun(run_slug="(pending)", name="pj", status="pending", benchmark_id=bm.id)
        s.add(run)
        s.flush()
        bid, rid = bm.id, run.id

    async def fake_eval(config, cases, adapter, judges, *, progress=None,
                        run_name=None, account_owner="", out_dir=None, resume_dir=None):
        # 模拟内核落盘：在给定 out_dir 写下 traces.jsonl.gz。
        assert out_dir is not None and run_name is not None
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "traces.jsonl.gz").write_bytes(b"gz")
        return make_report(run_name)

    pruned: dict = {}
    monkeypatch.setattr("server.eval_job.evaluate", fake_eval)
    monkeypatch.setattr("server.eval_job.load_benchmark_cases", lambda *a, **k: [])
    monkeypatch.setattr(
        "server.eval_job.retention.prune_outputs",
        lambda *a, **k: pruned.update(called=True) or None,
    )

    job = build_eval_job(rid, benchmark_id=bid, run_name="pj", settings=settings)
    asyncio.run(job(InMemoryProgress()))

    with session_scope() as s:
        row = s.get(EvalRun, rid)
        assert row.status == "success"
        assert row.has_traces is True
    assert pruned.get("called") is True


def test_incremental_results_are_visible_and_finalization_is_idempotent(
    initialized_db,
):
    report = make_report("incremental_run")
    with session_scope() as session:
        row = EvalRun(
            run_slug="(pending)", name="增量评测", status="running", n_runs=1
        )
        session.add(row)
        session.flush()
        run_id = row.id

    persister = IncrementalRunPersister(
        run_id,
        run_name=report.run_name,
        adapter_type=report.adapter_type,
        config_snapshot=report.config_snapshot,
        description=report.description,
        n_runs=report.n_runs,
        sample_order=[result.case.sample_id for result in report.results],
    )

    asyncio.run(persister(report.results[0]))
    asyncio.run(persister(report.results[0]))
    with session_scope() as session:
        row = session.get(EvalRun, run_id)
        assert row.status == "running"
        assert row.finished_at is None
        assert row.total == 1
        assert session.query(CaseResultRow).filter_by(run_id=run_id).count() == 1

    asyncio.run(persister(report.results[1]))
    with session_scope() as session:
        row = session.get(EvalRun, run_id)
        assert row.status == "running"
        assert row.total == 2
        assert session.query(CaseResultRow).filter_by(run_id=run_id).count() == 2
        finalize_run(session, row, report)

    with session_scope() as session:
        row = session.get(EvalRun, run_id)
        assert row.status == "success"
        assert row.total == 2
        assert session.query(CaseResultRow).filter_by(run_id=run_id).count() == 2


# ---------------------------------------------------------------------------
# 3. 离线重判 job：仅判分、产出新 run、parent_run_id 指向源


def test_rejudge_job_replays_frozen_traces(initialized_db, settings, monkeypatch):
    src_id = _seed_source_run(settings, with_traces=True, n_runs=1)
    with session_scope() as s:
        new = EvalRun(run_slug="(pending)", name="重判", status="pending", parent_run_id=src_id)
        s.add(new)
        s.flush()
        new_id = new.id

    captured: dict = {}

    async def fake_judge(config, cases, per_case_traces, judges, *,
                         progress=None, run_name=None, declare_plan=True, **kw):
        captured["sample_ids"] = [c.sample_id for c in cases]
        captured["n_traces"] = sum(len(t) for t in per_case_traces)
        return make_report(run_name or "rj_2026-06-04_1")

    # 重判路径绝不调用 bot：evaluate 被调用即失败。
    async def boom(*a, **k):
        raise AssertionError("rejudge MUST NOT call evaluate (no bot calls)")

    monkeypatch.setattr("server.eval_job.judge_traces", fake_judge)
    monkeypatch.setattr("server.eval_job.evaluate", boom)

    job = build_rejudge_job(new_id, source_run_id=src_id, run_name="重判", settings=settings)
    asyncio.run(job(InMemoryProgress()))

    assert set(captured["sample_ids"]) == {"bc_001", "bc_002"}
    assert captured["n_traces"] == 2
    with session_scope() as s:
        row = s.get(EvalRun, new_id)
        assert row.status == "success"
        assert row.parent_run_id == src_id


# ---------------------------------------------------------------------------
# 4. 断点续跑 job：复用源留痕（resume_dir 指向源 run）


def test_resume_job_passes_resume_dir(initialized_db, settings, monkeypatch):
    src_id = _seed_source_run(settings, with_traces=True, n_runs=1)
    with session_scope() as s:
        new = EvalRun(run_slug="(pending)", name="续跑", status="pending", parent_run_id=src_id)
        s.add(new)
        s.flush()
        new_id = new.id

    captured: dict = {}

    async def fake_eval(config, cases, adapter, judges, *, progress=None,
                        run_name=None, account_owner="", out_dir=None, resume_dir=None):
        captured["resume_dir"] = resume_dir
        captured["out_dir"] = out_dir
        captured["sample_ids"] = [c.sample_id for c in cases]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "traces.jsonl.gz").write_bytes(b"gz")
        return make_report(run_name)

    monkeypatch.setattr("server.eval_job.evaluate", fake_eval)
    monkeypatch.setattr("server.eval_job.build_adapter", lambda *a, **k: object())

    job = build_resume_job(new_id, source_run_id=src_id, run_name="续跑", settings=settings)
    asyncio.run(job(InMemoryProgress()))

    assert captured["resume_dir"] == settings.outputs_dir / "src_2026-06-04_1"
    assert set(captured["sample_ids"]) == {"bc_001", "bc_002"}
    with session_scope() as s:
        row = s.get(EvalRun, new_id)
        assert row.status == "success"
        assert row.has_traces is True


# ---------------------------------------------------------------------------
# 4.5 单 Case 重试：真实调用+判分后原位替换，并同步 report.json


def test_retry_case_job_replaces_only_target_case(initialized_db, settings, monkeypatch):
    source = make_report("retry_2026-07-22_1")
    out_dir = settings.outputs_dir / source.run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(source.model_dump_json(), encoding="utf-8")
    target_id = source.results[0].case.sample_id

    with session_scope() as s:
        bm = Benchmark(name="retry-bm", source="uploaded", storage_path="/tmp/none")
        s.add(bm)
        s.flush()
        run = ingest_report(s, source, benchmark_id=bm.id)
        run_id = run.id

    async def fake_eval(config, cases, adapter, judges, *, progress=None, run_name=None, **kw):
        assert [case.sample_id for case in cases] == [target_id]
        retried = make_report(run_name)
        replacement = retried.results[0].model_copy(deep=True)
        replacement.case = cases[0]
        replacement.trace.error = None
        replacement.trace.messages[-1].content = "这是重试后的回答"
        retried.results = [replacement]
        return retried

    async def no_agent_chain(report, _settings):
        return None

    monkeypatch.setattr("server.eval_job.evaluate", fake_eval)
    monkeypatch.setattr("server.services.case_retry.build_eval_adapter", lambda config: object())
    monkeypatch.setattr("server.services.case_retry.build_judge_stack", lambda config: [])
    monkeypatch.setattr("server.services.case_retry.enrich_report_agent_chains", no_agent_chain)

    job = build_retry_case_job(run_id, sample_id=target_id, settings=settings)
    asyncio.run(job(InMemoryProgress()))

    with session_scope() as s:
        rows = s.query(CaseResultRow).filter(CaseResultRow.run_id == run_id).all()
        target = next(row for row in rows if row.sample_id == target_id)
        assert target.detail_json["trace"]["messages"][-1]["content"] == "这是重试后的回答"
        assert len(rows) == len(source.results)
        assert s.get(EvalRun, run_id).status == "success"
    persisted = make_report("unused").model_validate_json((out_dir / "report.json").read_text())
    assert persisted.results[0].trace.messages[-1].content == "这是重试后的回答"


def test_retry_case_endpoint_submits_current_run(client, settings, monkeypatch):
    source = make_report("retry_endpoint_2026-07-22")
    out_dir = settings.outputs_dir / source.run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(source.model_dump_json(), encoding="utf-8")
    target_id = source.results[0].case.sample_id
    with session_scope() as s:
        bm = Benchmark(name="retry-endpoint-bm", source="uploaded", storage_path="/tmp/none")
        s.add(bm)
        s.flush()
        run_id = ingest_report(s, source, benchmark_id=bm.id).id

    def noop_builder(run_id, *, sample_id):
        async def job(progress):
            return None
        return job

    class HoldingRunner:
        async def submit(self, run_id, job):
            return None

        def progress_snapshot(self, run_id):
            return {
                "current": None,
                "current_label": "",
                "done": 0,
                "total": 0,
                "percent": 0,
                "phases": {},
            }

    runner = HoldingRunner()
    monkeypatch.setattr("server.routers.runs.build_retry_case_job", noop_builder)
    monkeypatch.setattr(
        "server.routers.runs.rejudge.get_job_runner", lambda: runner
    )
    monkeypatch.setattr(
        "server.routers.runs.crud.get_job_runner", lambda: runner
    )
    response = client.post(f"/api/runs/{run_id}/cases/{target_id}/retry")

    assert response.status_code == 202, response.text
    assert response.json()["id"] == run_id
    progress = client.get(f"/api/runs/{run_id}/progress")
    assert progress.status_code == 200
    assert progress.json() == {
        "status": "pending",
        "progress": {
            "current": None,
            "current_label": "",
            "done": 0,
            "total": 0,
            "percent": 0,
            "phases": {},
            "context": {"kind": "case_retry", "sample_id": target_id},
        },
        "queue_position": None,
        "account_queue": {
            "enabled": False,
            "waiting_for_accounts": False,
            "pools": {},
        },
    }


def test_retry_cases_endpoint_submits_selected_cases(client, settings, monkeypatch):
    source = make_report("retry_cases_endpoint")
    out_dir = settings.outputs_dir / source.run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(source.model_dump_json(), encoding="utf-8")
    sample_ids = [result.case.sample_id for result in source.results]
    with session_scope() as session:
        benchmark = Benchmark(name="retry-cases-bm", source="uploaded", storage_path="/tmp/none")
        session.add(benchmark)
        session.flush()
        run_id = ingest_report(session, source, benchmark_id=benchmark.id).id

    received: list[str] = []

    def noop_builder(_run_id, *, sample_ids):
        received.extend(sample_ids)

        async def job(_progress):
            return None

        return job

    class HoldingRunner:
        async def submit(self, _run_id, _job):
            return None

    monkeypatch.setattr("server.routers.runs.build_retry_cases_job", noop_builder)
    monkeypatch.setattr("server.routers.runs.rejudge.get_job_runner", lambda: HoldingRunner())

    response = client.post(f"/api/runs/{run_id}/cases/retry", json={"sample_ids": sample_ids})

    assert response.status_code == 202, response.text
    assert received == sample_ids


def test_retry_cases_rejects_when_source_run_has_an_active_durable_job(client, settings, monkeypatch):
    source = make_report("retry_cases_active_job")
    out_dir = settings.outputs_dir / source.run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(source.model_dump_json(), encoding="utf-8")
    target_id = source.results[0].case.sample_id
    with session_scope() as session:
        benchmark = Benchmark(name="retry-cases-active-job-bm", source="uploaded", storage_path="/tmp/none")
        session.add(benchmark)
        session.flush()
        run_id = ingest_report(session, source, benchmark_id=benchmark.id).id

    class ActiveRunner:
        def queue_snapshot(self, _run_id):
            return {"state": "running", "position": 0}

        async def submit(self, _run_id, _job):
            raise AssertionError("有旧任务时不应提交新的重评任务")

    monkeypatch.setattr("server.routers.runs.rejudge.get_job_runner", lambda: ActiveRunner())
    response = client.post(f"/api/runs/{run_id}/cases/retry", json={"sample_ids": [target_id]})

    assert response.status_code == 409
    assert "已有运行中任务" in response.json()["detail"]
    with session_scope() as session:
        row = session.get(EvalRun, run_id)
        assert row.status == "success"
        assert row.progress == {}


# ---------------------------------------------------------------------------
# 5. 端点：rejudge 建新 run、resume 原地恢复、pin 落哨兵、缺留痕 400


def test_rejudge_endpoint_creates_pending_run(client, settings, monkeypatch):
    src_id = _seed_source_run(settings, with_traces=True, n_runs=1)

    def noop_builder(new_id, **kw):
        async def job(progress):
            return None
        return job

    monkeypatch.setattr("server.routers.runs.build_rejudge_job", noop_builder)

    resp = client.post(f"/api/runs/{src_id}/rejudge")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["parent_run_id"] == src_id
    assert body["id"] != src_id


def test_rejudge_endpoint_rejects_when_traces_pruned(client, settings):
    # n_runs>1 但无 traces.jsonl.gz → 无法重做 majority。
    src_id = _seed_source_run(settings, with_traces=False, n_runs=3)
    resp = client.post(f"/api/runs/{src_id}/rejudge")
    assert resp.status_code == 400


def test_resume_endpoint_restores_the_same_run(client, settings, monkeypatch):
    src_id = _seed_source_run(settings, with_traces=True, n_runs=1)

    def noop_builder(run_id, **kw):
        assert run_id == src_id
        assert kw["source_run_id"] == src_id
        assert kw["in_place"] is True

        async def job(progress):
            return None

        return job

    monkeypatch.setattr("server.routers.runs.build_resume_job", noop_builder)

    resp = client.post(f"/api/runs/{src_id}/resume")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"] == src_id
    assert body["parent_run_id"] is None
    assert body["status"] in {"pending", "running"}


def test_pin_endpoint_toggles_sentinel(client, settings):
    src_id = _seed_source_run(settings, with_traces=True, n_runs=1)
    out_dir = settings.outputs_dir / "src_2026-06-04_1"

    resp = client.post(f"/api/runs/{src_id}/pin", params={"pinned": True})
    assert resp.status_code == 200
    assert resp.json()["pinned"] is True
    assert (out_dir / "KEEP").exists()

    resp = client.post(f"/api/runs/{src_id}/pin", params={"pinned": False})
    assert resp.status_code == 200
    assert not (out_dir / "KEEP").exists()
