"""评测任务编排测试：打分模型覆盖合并 + finalize 落库（stub evaluate 避免网络）。"""

from __future__ import annotations

import asyncio

from factories import make_case, make_report

from medeval.models import Level
from server.db import session_scope
from server.eval_job import build_eval_job
from server.models_db import Benchmark, EvalRun
from server.progress import InMemoryProgress


def test_eval_job_merges_judge_model_and_finalizes(initialized_db, settings, monkeypatch):
    with session_scope() as s:
        bm = Benchmark(name="x", source="uploaded", storage_path="/tmp/none")
        s.add(bm)
        s.flush()
        run = EvalRun(run_slug="(pending)", name="x", status="pending", benchmark_id=bm.id)
        s.add(run)
        s.flush()
        bid, rid = bm.id, run.id

    captured: dict = {}

    async def fake_eval(config, cases, adapter, judges, adjudicator, *, progress=None, **kw):
        captured["config"] = config
        if progress:
            progress.start_phase("run", "调用 chatbot", 1)
            progress.advance("run")
        return make_report("jobrun_2026-06-03_1")

    monkeypatch.setattr("server.eval_job.evaluate", fake_eval)
    monkeypatch.setattr("server.eval_job.load_benchmark_cases", lambda *a, **k: [])

    job = build_eval_job(
        rid,
        benchmark_id=bid,
        run_name="jobrun",
        judge_full={"model": "gpt-4o-better", "provider": "openai", "api_key": "K"},
        settings=settings,
    )
    asyncio.run(job(InMemoryProgress()))

    # 打分模型已合并进 config 的 llm 与 scoring_point
    cfg = captured["config"]
    assert cfg.judges.llm.model == "gpt-4o-better"
    assert cfg.judges.scoring_point.model == "gpt-4o-better"

    # 评测结果已落库
    with session_scope() as s:
        row = s.get(EvalRun, rid)
        assert row.status == "success"
        assert row.total == 2
        assert row.run_slug == "jobrun_2026-06-03_1"
        assert len(row.case_results) == 2


def test_eval_job_filters_by_level(initialized_db, settings, monkeypatch):
    with session_scope() as s:
        bm = Benchmark(name="x", source="uploaded", storage_path="/tmp/none")
        s.add(bm)
        s.flush()
        run = EvalRun(run_slug="(pending)", name="x", status="pending", benchmark_id=bm.id)
        s.add(run)
        s.flush()
        bid, rid = bm.id, run.id

    captured: dict = {}

    async def fake_eval(config, cases, adapter, judges, adjudicator, *, progress=None, **kw):
        captured["cases"] = list(cases)
        return make_report("lvl_2026-06-03_1")

    monkeypatch.setattr("server.eval_job.evaluate", fake_eval)
    monkeypatch.setattr(
        "server.eval_job.load_benchmark_cases",
        lambda *a, **k: [
            make_case("a", level=Level.L1),
            make_case("b", level=Level.L3),
            make_case("c", level=Level.L3),
        ],
    )

    job = build_eval_job(rid, benchmark_id=bid, levels=["L3"], settings=settings)
    asyncio.run(job(InMemoryProgress()))

    got = captured["cases"]
    assert {c.sample_id for c in got} == {"b", "c"}
    assert all(c.level == Level.L3 for c in got)
