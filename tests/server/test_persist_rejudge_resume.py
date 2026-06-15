"""平台完整补齐：落 trace + has_traces、离线重判、断点续跑、置顶、附加列迁移。"""

from __future__ import annotations

import asyncio

from factories import make_report
from sqlalchemy import create_engine, inspect, text

from medeval import trace_store
from server.db import _ensure_additive_columns, session_scope
from server.eval_job import build_eval_job, build_rejudge_job, build_resume_job
from server.models_db import Benchmark, EvalRun
from server.progress import InMemoryProgress


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
# 1. 附加列幂等迁移


def test_ensure_additive_columns_on_legacy_table(tmp_path):
    """旧库（eval_run 缺新列）→ 迁移补齐，且可重复执行。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}", future=True)
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE eval_run (id INTEGER PRIMARY KEY, run_slug TEXT)")
        )

    _ensure_additive_columns(engine)
    _ensure_additive_columns(engine)  # 幂等：再跑一次不报错

    cols = {c["name"] for c in inspect(engine).get_columns("eval_run")}
    assert {"has_traces", "pinned", "parent_run_id"} <= cols


# ---------------------------------------------------------------------------
# 2. 平台正常评测：落 trace + has_traces + retention 收尾


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

    async def fake_eval(config, cases, adapter, judges, adjudicator, *, progress=None,
                        run_name=None, out_dir=None, resume_dir=None):
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

    async def fake_judge(config, cases, per_case_traces, judges, adjudicator, *,
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

    async def fake_eval(config, cases, adapter, judges, adjudicator, *, progress=None,
                        run_name=None, out_dir=None, resume_dir=None):
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
# 5. 端点：rejudge/resume 建新 run、pin 落哨兵、缺留痕 400


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


def test_resume_endpoint_creates_pending_run(client, settings, monkeypatch):
    src_id = _seed_source_run(settings, with_traces=True, n_runs=1)

    def noop_builder(new_id, **kw):
        async def job(progress):
            return None
        return job

    monkeypatch.setattr("server.routers.runs.build_resume_job", noop_builder)

    resp = client.post(f"/api/runs/{src_id}/resume")
    assert resp.status_code == 201, resp.text
    assert resp.json()["parent_run_id"] == src_id


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
