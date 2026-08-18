"""独立评测 Worker：通过 Postgres 租约领取任务，崩溃/部署后自动断点恢复。"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
import uuid

from .constants import EVAL_JOB_USER_ERROR
from .db import init_engine, session_scope
from .durable_jobs import build_job_from_payload
from .durable_queue import (
    acknowledge_cancel,
    claim_job,
    finish_job,
    heartbeat_job,
    job_status,
    requeue_job,
)
from .jobs import _set_status
from .models_db import EvalRun
from .progress import InMemoryProgress
from .settings import get_settings

logger = logging.getLogger("mme.worker")


def _restore_progress_floor(progress: InMemoryProgress, run_id: int) -> None:
    """从最后一次心跳恢复百分比下限，避免 Worker 重启后进度倒退。"""
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        snapshot = run.progress if run is not None and isinstance(run.progress, dict) else {}
    progress.restore_percent_floor(snapshot.get("percent"))


async def _execute_claimed(row, owner: str) -> None:
    settings = get_settings()
    progress = InMemoryProgress()
    is_attribution = row.kind == "attribution"

    def _mark_attribution_failure(error: str) -> None:
        if not is_attribution:
            return
        task_id = int((row.payload or {}).get("attribution_task_id") or 0)
        if task_id <= 0:
            return
        from .services.attribution_tasks import mark_attribution_task_worker_failed

        mark_attribution_task_worker_failed(task_id, error)
    if not is_attribution and (int(row.attempts or 0) > 1 or row.kind == "resume"):
        _restore_progress_floor(progress, row.run_id)
    if not is_attribution:
        _set_status(row.run_id, "running")
    try:
        job = build_job_from_payload(row.run_id, row.kind, dict(row.payload or {}), settings)
    except Exception:  # noqa: BLE001
        logger.exception("无法还原评测任务 job_id=%s run_id=%s", row.id, row.run_id)
        finish_job(row.id, owner, "failed", error=EVAL_JOB_USER_ERROR)
        _mark_attribution_failure("无法恢复持久化归因任务")
        if not is_attribution:
            _set_status(row.run_id, "failed", error=EVAL_JOB_USER_ERROR)
        return
    task = asyncio.create_task(job(progress), name=f"evaluation-job-{row.id}")
    interrupted = False
    try:
        while not task.done():
            try:
                await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=max(1, settings.job_heartbeat_seconds),
                )
            except asyncio.TimeoutError:
                if not heartbeat_job(
                    row.id,
                    owner,
                    settings.job_lease_seconds,
                    # 归因的进度由 attribution_task / item 分表维护，不能覆盖
                    # 已完成评测 Run 的进度快照。
                    progress=None if is_attribution else progress.snapshot(),
                ):
                    interrupted = True
                    task.cancel()
                    break
        if interrupted:
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            if job_status(row.id) == "cancelled":
                acknowledge_cancel(row.id, owner)
            return
        await task
    except asyncio.CancelledError:
        externally_cancelled = bool(asyncio.current_task() and asyncio.current_task().cancelling())
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        # 用户取消是终态；Worker 停止/部署才重新排队。
        current_status = job_status(row.id)
        if current_status == "running":
            requeue_job(row.id, owner)
        elif current_status == "cancelled":
            acknowledge_cancel(row.id, owner)
        if externally_cancelled:
            raise
        return
    except Exception:  # noqa: BLE001
        if job_status(row.id) == "cancelled":
            acknowledge_cancel(row.id, owner)
            return
        logger.exception("%s任务失败 job_id=%s run_id=%s", "归因" if is_attribution else "评测", row.id, row.run_id)
        finish_job(row.id, owner, "failed", error=EVAL_JOB_USER_ERROR)
        _mark_attribution_failure("Worker 执行异常")
        if not is_attribution:
            _set_status(
                row.run_id,
                "failed",
                error=EVAL_JOB_USER_ERROR,
                progress=progress.snapshot(),
            )
    else:
        if finish_job(row.id, owner, "succeeded"):
            if not is_attribution:
                _set_status(row.run_id, "success", progress=progress.snapshot())


async def _worker_slot(slot: int, owner_prefix: str) -> None:
    settings = get_settings()
    owner = f"{owner_prefix}:{slot}"
    while True:
        row = claim_job(owner, settings.job_lease_seconds)
        if row is None:
            await asyncio.sleep(max(0.2, settings.job_poll_seconds))
            continue
        logger.info(
            "领取评测任务 job_id=%s run_id=%s kind=%s attempt=%s",
            row.id,
            row.run_id,
            row.kind,
            row.attempts,
        )
        try:
            await _execute_claimed(row, owner)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - 单条任务异常不能杀死整个 Worker slot
            logger.exception("Worker slot 异常 slot=%s job_id=%s", slot, row.id)


async def run_worker() -> None:
    settings = get_settings()
    settings.check_production_security()
    # 数据库建表和历史迁移只由 Web 进程执行。主机重启时 Worker 与 Web 会同时
    # 自动拉起；若这里也执行 init_db，两边会并发扫描并重写大 JSON，造成 WAL
    # 写放大和磁盘 I/O 饱和。Worker 只初始化连接并等待 Web 完成建表。
    init_engine(settings)
    await _wait_for_schema()
    owner = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # pragma: no cover - Windows
            pass
    slots = [
        asyncio.create_task(_worker_slot(i + 1, owner), name=f"worker-slot-{i + 1}")
        for i in range(max(1, settings.max_concurrent_jobs))
    ]
    logger.info("评测 Worker 已启动 owner=%s slots=%s", owner, len(slots))
    await stop.wait()
    for task in slots:
        task.cancel()
    await asyncio.gather(*slots, return_exceptions=True)
    logger.info("评测 Worker 已停止；在跑任务已重新排队")


async def _wait_for_schema() -> None:
    """等待 Web 进程完成轻量建表/迁移，避免新环境启动竞态。"""
    from sqlalchemy import select
    from sqlalchemy.exc import SQLAlchemyError

    from .models_db import EvaluationJob

    while True:
        try:
            with session_scope() as session:
                session.execute(select(EvaluationJob.id).limit(1)).first()
            return
        except SQLAlchemyError:
            logger.info("等待 Web 服务完成数据库初始化")
            await asyncio.sleep(2)


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, os.environ.get("MEDEVAL_LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
