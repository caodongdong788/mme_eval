"""续跑可恢复被服务重启中断的 run（无 report.json，仅 partial 留痕）+ plan.json 落盘。"""

from __future__ import annotations

import asyncio
import json

from factories import make_case, make_report

from medeval import trace_store
from medeval.models import ConversationTrace
from server.db import session_scope
from server.eval_job import build_eval_job, build_resume_job
from server.models_db import Benchmark, EvalRun
from server.progress import InMemoryProgress


def _write_partial(out_dir, succeeded_sample_ids, *, n_runs=1, n_cases=2):
    """在 out_dir 写一份 traces.partial.jsonl（模拟跑到一半被打断、无 report.json）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    w = trace_store.PartialTraceWriter(
        out_dir,
        store_raw="on_error",
        meta={
            "schema": trace_store.SCHEMA_VERSION,
            "adapter_fingerprint": "fp-src",
            "store_raw": "on_error",
            "n_runs": n_runs,
            "n_cases": n_cases,
        },
    )
    for i, sid in enumerate(succeeded_sample_ids):
        w.record(sid, i, 0, ConversationTrace(messages=[], error=None))
    w.close()


def _seed_interrupted_run(settings, *, slug="src_interrupted_2026-06-05_1", plan_ids=None):
    """造一个被中断的源 run：只有 partial 留痕 + 可选 plan.json，无 report.json，DB status=failed。"""
    out_dir = settings.outputs_dir / slug
    _write_partial(out_dir, ["bc_001"], n_runs=1, n_cases=2)
    if plan_ids is not None:
        (out_dir / "plan.json").write_text(
            json.dumps({"sample_ids": plan_ids, "n_runs": 1}), encoding="utf-8"
        )
    with session_scope() as s:
        bm = Benchmark(name="src-bm", source="uploaded", storage_path="/tmp/none")
        s.add(bm)
        s.flush()
        row = EvalRun(
            run_slug=slug,
            name="中断评测",
            status="failed",
            error_msg="服务重启导致任务中断（孤儿任务回收）",
            benchmark_id=bm.id,
            n_runs=1,
            has_traces=False,
        )
        s.add(row)
        s.flush()
        return row.id, out_dir


# ---------------------------------------------------------------------------
# 1. 续跑 job：源 run 无 report.json 时从 benchmark + plan.json 重建用例集


def test_resume_rebuilds_cases_from_benchmark_when_no_report(
    initialized_db, settings, monkeypatch
):
    src_id, src_dir = _seed_interrupted_run(settings, plan_ids=["bc_001", "bc_002"])
    with session_scope() as s:
        new = EvalRun(run_slug="(pending)", name="续跑", status="pending", parent_run_id=src_id)
        s.add(new)
        s.flush()
        new_id = new.id

    captured: dict = {}

    # benchmark 含 3 条；plan.json 限定为前两条 → 续跑用例集应只含 bc_001/bc_002（按 plan 顺序）。
    bench_cases = [make_case("bc_001"), make_case("bc_002"), make_case("bc_003")]
    monkeypatch.setattr("server.eval_job.load_benchmark_cases", lambda *a, **k: bench_cases)

    async def fake_eval(config, cases, adapter, judges, adjudicator, *, progress=None,
                        run_name=None, out_dir=None, resume_dir=None):
        captured["resume_dir"] = resume_dir
        captured["sample_ids"] = [c.sample_id for c in cases]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "traces.jsonl.gz").write_bytes(b"gz")
        return make_report(run_name)

    monkeypatch.setattr("server.eval_job.evaluate", fake_eval)
    monkeypatch.setattr("server.eval_job.build_adapter", lambda *a, **k: object())

    job = build_resume_job(new_id, source_run_id=src_id, run_name="续跑", settings=settings)
    asyncio.run(job(InMemoryProgress()))

    assert captured["resume_dir"] == src_dir
    assert captured["sample_ids"] == ["bc_001", "bc_002"]
    with session_scope() as s:
        assert s.get(EvalRun, new_id).status == "success"


def test_resume_falls_back_to_full_benchmark_without_plan(
    initialized_db, settings, monkeypatch
):
    src_id, _ = _seed_interrupted_run(
        settings, slug="src_noplan_2026-06-05_1", plan_ids=None
    )
    with session_scope() as s:
        new = EvalRun(run_slug="(pending)", name="续跑", status="pending", parent_run_id=src_id)
        s.add(new)
        s.flush()
        new_id = new.id

    captured: dict = {}
    bench_cases = [make_case("bc_001"), make_case("bc_002"), make_case("bc_003")]
    monkeypatch.setattr("server.eval_job.load_benchmark_cases", lambda *a, **k: bench_cases)

    async def fake_eval(config, cases, adapter, judges, adjudicator, *, progress=None,
                        run_name=None, out_dir=None, resume_dir=None):
        captured["sample_ids"] = [c.sample_id for c in cases]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "traces.jsonl.gz").write_bytes(b"gz")
        return make_report(run_name)

    monkeypatch.setattr("server.eval_job.evaluate", fake_eval)
    monkeypatch.setattr("server.eval_job.build_adapter", lambda *a, **k: object())

    job = build_resume_job(new_id, source_run_id=src_id, run_name="续跑", settings=settings)
    asyncio.run(job(InMemoryProgress()))

    # 无 plan.json → 回退源 benchmark 全量。
    assert captured["sample_ids"] == ["bc_001", "bc_002", "bc_003"]


# ---------------------------------------------------------------------------
# 2. 评测启动落 plan.json（捕获过滤后的实际用例集）


def test_eval_job_writes_plan_json(initialized_db, settings, monkeypatch):
    with session_scope() as s:
        bm = Benchmark(name="x", source="uploaded", storage_path="/tmp/none")
        s.add(bm)
        s.flush()
        run = EvalRun(run_slug="(pending)", name="pj", status="pending", benchmark_id=bm.id)
        s.add(run)
        s.flush()
        bid, rid = bm.id, run.id

    monkeypatch.setattr(
        "server.eval_job.load_benchmark_cases",
        lambda *a, **k: [make_case("bc_001"), make_case("bc_002")],
    )

    captured: dict = {}

    async def fake_eval(config, cases, adapter, judges, adjudicator, *, progress=None,
                        run_name=None, out_dir=None, resume_dir=None):
        captured["out_dir"] = out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "traces.jsonl.gz").write_bytes(b"gz")
        return make_report(run_name)

    monkeypatch.setattr("server.eval_job.evaluate", fake_eval)
    monkeypatch.setattr("server.eval_job.build_adapter", lambda *a, **k: object())
    monkeypatch.setattr("server.eval_job.retention.prune_outputs", lambda *a, **k: None)

    job = build_eval_job(rid, benchmark_id=bid, run_name="pj", settings=settings)
    asyncio.run(job(InMemoryProgress()))

    plan_path = captured["out_dir"] / "plan.json"
    assert plan_path.is_file()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["sample_ids"] == ["bc_001", "bc_002"]
    assert plan["n_runs"] == 1


# ---------------------------------------------------------------------------
# 3. 端点：接受中断 run（无 report、有 partial），无任何留痕则拒绝


def test_resume_endpoint_accepts_interrupted_run(client, settings, monkeypatch):
    src_id, _ = _seed_interrupted_run(settings, plan_ids=["bc_001", "bc_002"])

    def noop_builder(new_id, **kw):
        async def job(progress):
            return None
        return job

    monkeypatch.setattr("server.routers.runs.build_resume_job", noop_builder)

    resp = client.post(f"/api/runs/{src_id}/resume")
    assert resp.status_code == 201, resp.text
    assert resp.json()["parent_run_id"] == src_id


def test_resume_endpoint_rejects_when_no_traces_at_all(client, settings):
    slug = "src_empty_2026-06-05_1"
    (settings.outputs_dir / slug).mkdir(parents=True, exist_ok=True)
    with session_scope() as s:
        bm = Benchmark(name="b", source="uploaded", storage_path="/tmp/none")
        s.add(bm)
        s.flush()
        row = EvalRun(
            run_slug=slug, name="空", status="failed", benchmark_id=bm.id, n_runs=1
        )
        s.add(row)
        s.flush()
        src_id = row.id

    resp = client.post(f"/api/runs/{src_id}/resume")
    assert resp.status_code == 400
    assert "留痕" in resp.json()["detail"]
