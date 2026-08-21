"""评测任务调度。

``JobRunner`` 抽象出「提交评测任务 + 跟踪状态/进度」。开发/测试可用进程内 asyncio；
生产使用数据库租约队列，由独立 Worker 执行并在部署或崩溃后断点恢复。
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime

from sqlalchemy import select

from .constants import EVAL_JOB_USER_ERROR
from .db import session_scope
from .job_specs import get_job_spec, JobFn, without_api_keys
from .models_db import EvalRun, EvaluationJob
from .progress import InMemoryProgress
from .settings import get_settings

log = logging.getLogger(__name__)

class JobRunner(ABC):
    @abstractmethod
    async def submit(self, run_id: int, job: JobFn) -> "asyncio.Task | None": ...

    @abstractmethod
    def progress_snapshot(self, run_id: int) -> dict | None: ...

    async def cancel(self, run_id: int) -> bool:
        """终止指定任务。默认实现兼容不支持主动取消的调度器。"""
        return False

    def queue_snapshot(self, run_id: int) -> dict | None:
        """任务调度队列状态；非进程内实现可按需覆盖。"""
        return None

    async def shutdown(self) -> None:
        """优雅关闭钩子：默认 no-op，子类按需取消在跑任务。"""
        return None


def reconcile_orphaned_runs() -> int:
    """回收孤儿任务：把 running/pending 的 run 置为 failed（启动时调用）。

    进程内调度的任务态仅存于内存，进程重启/热重载/崩溃会杀掉在跑任务而 DB 状态停在
    running/pending。新进程启动时不可能有存活任务，故此回收安全且必要，使这些 run 可删、
    状态正确。返回回收条数；对 success/failed 无副作用，重复调用幂等。
    """
    from sqlalchemy import select

    count = 0
    with session_scope() as session:
        rows = session.execute(
            select(EvalRun).where(EvalRun.status.in_(("running", "pending")))
        ).scalars().all()
        for row in rows:
            row.status = "failed"
            row.error_msg = "服务重启导致任务中断（孤儿任务回收）"
            row.progress = {}
            if row.finished_at is None:
                row.finished_at = datetime.utcnow()
            count += 1
    return count


def _set_status(
    run_id: int,
    status: str,
    *,
    error: str = "",
    progress: dict | None = None,
) -> None:
    with session_scope() as session:
        row = session.get(EvalRun, run_id)
        if row is None:
            return
        # 独立 Worker 已成功收敛的 Job 是最终真值。忽略旧进程/迟到协程针对
        # 同一已成功 Job 的通用失败回写，避免部署窗口把完成任务重新显示为失败。
        if status == "failed" and row.status == "success":
            latest_job = session.scalar(
                select(EvaluationJob)
                .where(
                    EvaluationJob.run_id == run_id,
                    EvaluationJob.kind.in_(("evaluation", "resume", "rejudge", "cases_retry")),
                )
                .order_by(EvaluationJob.id.desc())
            )
            if latest_job is not None and latest_job.status == "succeeded":
                return
        row.status = status
        if status == "running" and row.started_at is None:
            row.started_at = datetime.utcnow()
        if status in ("success", "failed") and row.finished_at is None:
            row.finished_at = datetime.utcnow()
        if status in ("success", "failed"):
            # 批量/单条重新评测结束后，保留用例范围与最终进度，供刷新页面后
            # 继续展示这一次操作的完成状态。普通任务仍维持原先清空进度的语义。
            context = row.progress.get("context") if isinstance(row.progress, dict) else None
            if isinstance(context, dict) and context.get("kind") in {"case_retry", "cases_retry"}:
                row.progress = {**(progress or {}), "context": dict(context), "completed": status == "success"}
            else:
                row.progress = {}
        if error:
            row.error_msg = error[:4000]


class InProcessJobRunner(JobRunner):
    """进程内 asyncio 任务调度，并发受 Semaphore 限流。"""

    def __init__(self, max_concurrent: int = 2) -> None:
        self._max_concurrent = max(1, max_concurrent)
        self._sem: asyncio.Semaphore | None = None
        self._progress: dict[int, InMemoryProgress] = {}
        self._tasks: dict[int, asyncio.Task] = {}
        self._states: dict[int, str] = {}
        self._submitted_order: dict[int, int] = {}
        self._next_order = 0

    def _semaphore(self) -> asyncio.Semaphore:
        # 惰性创建：绑定到首次 await 时的事件循环。
        if self._sem is None:
            self._sem = asyncio.Semaphore(self._max_concurrent)
        return self._sem

    async def submit(self, run_id: int, job: JobFn) -> asyncio.Task:
        progress = InMemoryProgress()
        self._progress[run_id] = progress
        self._states[run_id] = "queued"
        self._next_order += 1
        self._submitted_order[run_id] = self._next_order
        task = asyncio.create_task(self._run(run_id, job, progress))
        self._tasks[run_id] = task
        return task

    async def _run(self, run_id: int, job: JobFn, progress: InMemoryProgress) -> None:
        async with self._semaphore():
            self._states[run_id] = "running"
            _set_status(run_id, "running")
            try:
                await job(progress)
            except Exception as exc:  # noqa: BLE001 —— 失败兜底落 error_msg
                log.exception("eval job run_id=%s failed", run_id)
                _set_status(
                    run_id,
                    "failed",
                    error=EVAL_JOB_USER_ERROR,
                    progress=progress.snapshot(),
                )
            else:
                _set_status(run_id, "success", progress=progress.snapshot())
                from .services.deeptrace_automation import report_run_completion

                await report_run_completion(run_id)
            finally:
                self._states[run_id] = "done"

    def progress_snapshot(self, run_id: int) -> dict | None:
        p = self._progress.get(run_id)
        return p.snapshot() if p else None

    async def cancel(self, run_id: int) -> bool:
        """取消运行中或排队中的任务，并等待协程完全退出后再允许删除记录。"""
        task = self._tasks.get(run_id)
        if task is None or task.done():
            return False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            self._tasks.pop(run_id, None)
            self._progress.pop(run_id, None)
            self._states.pop(run_id, None)
            self._submitted_order.pop(run_id, None)
        return True

    def queue_snapshot(self, run_id: int) -> dict | None:
        state = self._states.get(run_id)
        if state is None or state == "done":
            return None
        if state == "running":
            return {"state": "running", "position": 0}
        queued = sorted(
            (
                (order, queued_run_id)
                for queued_run_id, order in self._submitted_order.items()
                if self._states.get(queued_run_id) == "queued"
            ),
        )
        position = next(
            (index for index, (_order, queued_run_id) in enumerate(queued, start=1) if queued_run_id == run_id),
            None,
        )
        return {"state": "queued", "position": position}

    async def shutdown(self) -> None:
        """取消所有在跑任务并等待其结束（被取消的 run 由下次启动 reconcile 回收）。"""
        tasks = [t for t in self._tasks.values() if not t.done()]
        for t in tasks:
            t.cancel()
        for t in tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):  # noqa: BLE001 —— 关闭阶段吞掉残余异常
                pass


class DatabaseJobRunner(JobRunner):
    """API 进程只把任务写入数据库，由独立 Worker 领取执行。"""

    async def submit(self, run_id: int, job: JobFn) -> None:
        from .durable_queue import enqueue_job

        spec = get_job_spec(job)
        if spec is None:
            raise ValueError("持久化调度要求 Job 提供可序列化任务描述")
        enqueue_job(run_id, spec.kind, without_api_keys(spec.payload))
        return None

    def progress_snapshot(self, run_id: int) -> dict | None:
        from .durable_queue import progress_snapshot

        return progress_snapshot(run_id)

    def queue_snapshot(self, run_id: int) -> dict | None:
        from .durable_queue import queue_snapshot

        return queue_snapshot(run_id)

    async def cancel(self, run_id: int) -> bool:
        from .durable_queue import cancel_job, job_is_executing

        cancelled = cancel_job(run_id)
        if not cancelled:
            return False
        # 删除接口必须等 Worker 停止写入后再删 Run/产物，避免跨进程取消的竞态。
        deadline = asyncio.get_running_loop().time() + get_settings().job_heartbeat_seconds + 5
        while job_is_executing(run_id) and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.2)
        return True


def enqueue_database_job_in_session(
    session,
    job_runner: JobRunner,
    run_id: int,
    job: JobFn,
) -> bool:
    """数据库调度模式下把任务加入调用方事务；其他模式返回 False。

    这使 Run 的 pending 状态和 EvaluationJob 同时提交或同时回滚，杜绝只创建
    Run、没有执行任务的僵尸记录。
    """
    if not isinstance(job_runner, DatabaseJobRunner):
        return False
    from .durable_queue import enqueue_job_in_session

    spec = get_job_spec(job)
    if spec is None:
        raise ValueError("持久化调度要求 Job 提供可序列化任务描述")
    enqueue_job_in_session(
        session,
        run_id,
        spec.kind,
        without_api_keys(spec.payload),
    )
    return True


async def commit_and_submit_job(
    session,
    run_id: int,
    job: JobFn,
    *,
    job_runner: JobRunner | None = None,
    failure_message: str = "任务提交执行队列失败",
) -> None:
    """原子提交数据库任务，并为进程内调度提供失败补偿。"""
    runner = job_runner or get_job_runner()
    if enqueue_database_job_in_session(session, runner, run_id, job):
        session.commit()
        return

    # 进程内任务必须先看到已提交的 Run；submit 只创建协程，不等待业务执行。
    if hasattr(session, "commit"):
        session.commit()
    try:
        await runner.submit(run_id, job)
    except BaseException as exc:
        if not hasattr(session, "get"):
            raise
        session.rollback()
        row = session.get(EvalRun, run_id)
        if row is not None and row.status == "pending":
            row.status = "failed"
            row.finished_at = datetime.utcnow()
            row.error_msg = f"{failure_message}：{exc}"[:4000]
            session.commit()
        raise


_runner: JobRunner | None = None


def get_job_runner() -> JobRunner:
    global _runner
    if _runner is None:
        settings = get_settings()
        if settings.job_runner_mode == "database":
            _runner = DatabaseJobRunner()
        else:
            _runner = InProcessJobRunner(settings.max_concurrent_jobs)
    return _runner


def reset_job_runner_for_tests() -> None:
    global _runner
    _runner = None
