"""JobRunner 测试：状态机、失败兜底、并发上限、进度可查询。"""

from __future__ import annotations

import asyncio

from server.db import session_scope
from server.jobs import InProcessJobRunner
from server.models_db import EvalRun
from server.progress import InMemoryProgress


def _new_pending_run() -> int:
    with session_scope() as s:
        row = EvalRun(run_slug="t", name="t", status="pending")
        s.add(row)
        s.flush()
        return row.id


def _status(run_id: int) -> str:
    with session_scope() as s:
        return s.get(EvalRun, run_id).status


def test_job_success_sets_status_and_progress(initialized_db):
    run_id = _new_pending_run()
    runner = InProcessJobRunner(max_concurrent=2)

    async def job(progress):
        progress.start_phase("run", "调用 chatbot", 2)
        progress.advance("run")
        await asyncio.sleep(0)
        progress.advance("run")

    async def scenario():
        task = await runner.submit(run_id, job)
        await task

    asyncio.run(scenario())
    assert _status(run_id) == "success"
    snap = runner.progress_snapshot(run_id)
    assert snap["done"] == 2 and snap["total"] == 2 and snap["percent"] == 100.0


def test_job_failure_records_error(initialized_db):
    run_id = _new_pending_run()
    runner = InProcessJobRunner(max_concurrent=2)

    async def job(progress):
        raise RuntimeError("boom")

    async def scenario():
        task = await runner.submit(run_id, job)
        await task

    asyncio.run(scenario())
    assert _status(run_id) == "failed"
    with session_scope() as s:
        row = s.get(EvalRun, run_id)
        assert "boom" in row.error_msg
        assert row.finished_at is not None


def test_progress_percent_monotonic_across_phases():
    # 声明完整阶段计划后，跨阶段推进百分比必须单调不回退（修复「近 100% 回到 0%」）。
    p = InMemoryProgress()
    p.plan_phases(
        [
            ("run", "调用 chatbot", 4),
            ("judge_det", "Judge 判分 (确定性)", 4),
            ("judge_llm", "Judge 判分 (LLM)", 2),
            ("judge_sp", "Judge 判分 (得分点)", 2),
        ]
    )

    percents: list[float] = [p.snapshot()["percent"]]

    p.start_phase("run", "调用 chatbot", 4)
    for _ in range(4):
        p.advance("run")
        percents.append(p.snapshot()["percent"])
    # 首阶段满载，但全局尚未完成 → 严格 < 100。
    assert percents[-1] < 100.0

    p.start_phase("judge_det", "Judge 判分 (确定性)", 4)
    # 切阶段瞬间不得回退。
    assert p.snapshot()["percent"] >= percents[-1]
    for _ in range(4):
        p.advance("judge_det")
        percents.append(p.snapshot()["percent"])

    p.start_phase("judge_llm", "Judge 判分 (LLM)", 2)
    assert p.snapshot()["percent"] >= percents[-1]
    for _ in range(2):
        p.advance("judge_llm")
        percents.append(p.snapshot()["percent"])

    p.start_phase("judge_sp", "Judge 判分 (得分点)", 2)
    assert p.snapshot()["percent"] >= percents[-1]
    for _ in range(2):
        p.advance("judge_sp")
        percents.append(p.snapshot()["percent"])

    # 全程单调非降，且最终满载 == 100。
    assert all(b >= a for a, b in zip(percents, percents[1:])), percents
    assert percents[-1] == 100.0


def test_progress_percent_falls_back_to_current_phase_without_plan():
    # 未声明阶段计划时，保持原「当前阶段」口径（向后兼容）。
    p = InMemoryProgress()
    p.start_phase("run", "调用 chatbot", 4)
    p.advance("run")
    p.advance("run")
    assert p.snapshot()["percent"] == 50.0


def test_concurrency_limit_respected(initialized_db):
    runner = InProcessJobRunner(max_concurrent=2)
    run_ids = [_new_pending_run() for _ in range(4)]

    state = {"active": 0, "peak": 0}

    async def job(progress):
        state["active"] += 1
        state["peak"] = max(state["peak"], state["active"])
        await asyncio.sleep(0.05)
        state["active"] -= 1

    async def scenario():
        tasks = [await runner.submit(rid, job) for rid in run_ids]
        await asyncio.gather(*tasks)

    asyncio.run(scenario())
    assert state["peak"] <= 2
    assert all(_status(rid) == "success" for rid in run_ids)
