"""线上评测后台任务调度与孤儿任务回收。"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select

from .db import session_scope
from .models_db import OnlineEval
from .services.online_evals import run_online_eval

log = logging.getLogger(__name__)


def reconcile_orphaned_online_evals() -> int:
    """启动时把 pending/running 的线上评测置 failed。"""
    count = 0
    with session_scope() as session:
        rows = session.execute(
            select(OnlineEval).where(OnlineEval.status.in_(("pending", "running")))
        ).scalars().all()
        for row in rows:
            row.status = "failed"
            row.error_msg = "服务重启导致线上评测中断（孤儿任务回收）"
            if row.finished_at is None:
                row.finished_at = datetime.utcnow()
            count += 1
    return count


class OnlineEvalJobRunner:
    def __init__(self, max_concurrent: int = 2) -> None:
        self._max_concurrent = max(1, max_concurrent)
        self._sem: asyncio.Semaphore | None = None
        self._tasks: dict[int, asyncio.Task] = {}

    def _semaphore(self) -> asyncio.Semaphore:
        if self._sem is None:
            self._sem = asyncio.Semaphore(self._max_concurrent)
        return self._sem

    async def submit(self, eval_id: int) -> asyncio.Task:
        task = asyncio.create_task(self._run(eval_id))
        self._tasks[eval_id] = task
        return task

    async def _run(self, eval_id: int) -> None:
        async with self._semaphore():
            try:
                await run_online_eval(eval_id)
            except Exception:  # noqa: BLE001
                log.exception("online eval job eval_id=%s failed", eval_id)

    async def shutdown(self) -> None:
        tasks = [task for task in self._tasks.values() if not task.done()]
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass


_runner: OnlineEvalJobRunner | None = None


def get_online_eval_job_runner() -> OnlineEvalJobRunner:
    global _runner
    if _runner is None:
        from .settings import get_settings

        _runner = OnlineEvalJobRunner(get_settings().max_concurrent_jobs)
    return _runner


def reset_online_eval_job_runner_for_tests() -> None:
    global _runner
    _runner = None
