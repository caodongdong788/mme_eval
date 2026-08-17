"""JobRunner 测试：状态机、失败兜底、并发上限、进度可查询。"""

from __future__ import annotations

import asyncio

from server.constants import EVAL_JOB_USER_ERROR
from server.db import session_scope
from server.jobs import InProcessJobRunner
from server.models_db import EvalRun, EvaluationJob
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


def test_batch_case_retry_persists_case_progress_after_completion(initialized_db):
    run_id = _new_pending_run()
    with session_scope() as s:
        s.get(EvalRun, run_id).progress = {
            "context": {"kind": "cases_retry", "sample_ids": ["case_1", "case_2"]}
        }

    runner = InProcessJobRunner()

    async def job(progress):
        progress.set_case_total(2)
        await progress.case_completed(None)  # type: ignore[arg-type]
        await progress.case_completed(None)  # type: ignore[arg-type]

    async def scenario():
        task = await runner.submit(run_id, job)
        await task

    asyncio.run(scenario())
    with session_scope() as s:
        stored = s.get(EvalRun, run_id).progress
    assert stored["case_done"] == 2
    assert stored["case_total"] == 2
    assert stored["completed"] is True
    assert stored["context"]["sample_ids"] == ["case_1", "case_2"]


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
        assert row.error_msg == EVAL_JOB_USER_ERROR
        assert row.finished_at is not None


def test_late_failure_does_not_override_latest_successful_durable_job(initialized_db):
    """旧协程迟到回写失败时，不能覆盖持久化 Worker 的成功终态。"""
    from server.jobs import _set_status

    run_id = _new_pending_run()
    with session_scope() as s:
        run = s.get(EvalRun, run_id)
        assert run is not None
        run.status = "success"
        s.add(
            EvaluationJob(
                run_id=run_id,
                kind="evaluation",
                payload={},
                status="succeeded",
            )
        )

    _set_status(run_id, "failed", error=EVAL_JOB_USER_ERROR)
    with session_scope() as s:
        run = s.get(EvalRun, run_id)
        assert run is not None
        assert run.status == "success"
        assert run.error_msg == ""


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


def test_restored_progress_floor_prevents_worker_restart_regression():
    p = InMemoryProgress()
    p.restore_percent_floor(43.9)
    p.plan_phases(
        [
            ("run", "调用 chatbot", 63),
            ("judge_dimension", "Judge 判分 (八维)", 63),
            ("judge_guideline", "Judge 判分 (指南)", 63),
        ]
    )
    p.start_phase("judge_dimension", "Judge 判分 (八维)", 63)
    p.start_phase("judge_guideline", "Judge 判分 (指南)", 63)
    p.start_phase("run", "调用 chatbot", 63)

    assert p.snapshot()["percent"] == 43.9
    p.advance("run", 63)
    p.advance("judge_dimension", 20)
    p.advance("judge_guideline", 20)
    assert p.snapshot()["percent"] > 43.9


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


def test_queue_snapshot_reports_waiting_job_position(initialized_db):
    runner = InProcessJobRunner(max_concurrent=1)
    first_id, second_id = _new_pending_run(), _new_pending_run()
    first_started = asyncio.Event()
    release_first = asyncio.Event()

    async def first_job(_progress):
        first_started.set()
        await release_first.wait()

    async def second_job(_progress):
        return None

    async def scenario():
        first = await runner.submit(first_id, first_job)
        await first_started.wait()
        second = await runner.submit(second_id, second_job)
        await asyncio.sleep(0)
        assert runner.queue_snapshot(first_id) == {"state": "running", "position": 0}
        assert runner.queue_snapshot(second_id) == {"state": "queued", "position": 1}
        release_first.set()
        await asyncio.gather(first, second)

    asyncio.run(scenario())


def test_cancel_stops_running_job_and_clears_volatile_progress(initialized_db):
    run_id = _new_pending_run()
    runner = InProcessJobRunner(max_concurrent=1)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def job(_progress):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    async def scenario():
        task = await runner.submit(run_id, job)
        await started.wait()
        assert await runner.cancel(run_id) is True
        assert cancelled.is_set()
        assert task.cancelled()
        assert runner.progress_snapshot(run_id) is None
        assert runner.queue_snapshot(run_id) is None

    asyncio.run(scenario())
