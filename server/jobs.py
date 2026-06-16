"""评测任务调度。

``JobRunner`` 抽象出「异步执行一个评测任务 + 跟踪状态/进度」；MVP 用进程内 asyncio 实现
（并发上限、状态机 pending→running→success/failed）。未来上服务器水平扩展时，可换成基于
外部队列（Celery/RQ）的实现而不动 routers / eval 业务代码。
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import datetime

from .constants import EVAL_JOB_USER_ERROR
from .db import session_scope
from .models_db import EvalRun
from .progress import InMemoryProgress
from .settings import get_settings

log = logging.getLogger(__name__)

# 一个评测任务：拿到进度观察者，自行完成评测与落库（不负责状态流转）。
JobFn = Callable[[InMemoryProgress], Awaitable[None]]


class JobRunner(ABC):
    @abstractmethod
    async def submit(self, run_id: int, job: JobFn) -> "asyncio.Task | None": ...

    @abstractmethod
    def progress_snapshot(self, run_id: int) -> dict | None: ...

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
            if row.finished_at is None:
                row.finished_at = datetime.utcnow()
            count += 1
    return count


def _set_status(run_id: int, status: str, *, error: str = "") -> None:
    with session_scope() as session:
        row = session.get(EvalRun, run_id)
        if row is None:
            return
        row.status = status
        if status == "running" and row.started_at is None:
            row.started_at = datetime.utcnow()
        if status in ("success", "failed") and row.finished_at is None:
            row.finished_at = datetime.utcnow()
        if error:
            row.error_msg = error[:4000]


class InProcessJobRunner(JobRunner):
    """进程内 asyncio 任务调度，并发受 Semaphore 限流。"""

    def __init__(self, max_concurrent: int = 2) -> None:
        self._max_concurrent = max(1, max_concurrent)
        self._sem: asyncio.Semaphore | None = None
        self._progress: dict[int, InMemoryProgress] = {}
        self._tasks: dict[int, asyncio.Task] = {}

    def _semaphore(self) -> asyncio.Semaphore:
        # 惰性创建：绑定到首次 await 时的事件循环。
        if self._sem is None:
            self._sem = asyncio.Semaphore(self._max_concurrent)
        return self._sem

    async def submit(self, run_id: int, job: JobFn) -> asyncio.Task:
        progress = InMemoryProgress()
        self._progress[run_id] = progress
        task = asyncio.create_task(self._run(run_id, job, progress))
        self._tasks[run_id] = task
        return task

    async def _run(self, run_id: int, job: JobFn, progress: InMemoryProgress) -> None:
        async with self._semaphore():
            _set_status(run_id, "running")
            try:
                await job(progress)
            except Exception as exc:  # noqa: BLE001 —— 失败兜底落 error_msg
                log.exception("eval job run_id=%s failed", run_id)
                _set_status(run_id, "failed", error=EVAL_JOB_USER_ERROR)
                return
            _set_status(run_id, "success")

    def progress_snapshot(self, run_id: int) -> dict | None:
        p = self._progress.get(run_id)
        return p.snapshot() if p else None

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


_runner: JobRunner | None = None


def get_job_runner() -> JobRunner:
    global _runner
    if _runner is None:
        _runner = InProcessJobRunner(get_settings().max_concurrent_jobs)
    return _runner


def reset_job_runner_for_tests() -> None:
    global _runner
    _runner = None
