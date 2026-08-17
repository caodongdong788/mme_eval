"""基于数据库租约的评测队列，Postgres 多 Worker 可安全并发领取。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select

from .db import session_scope
from .models_db import EvalRun, EvaluationJob
from .paths import safe_join
from .settings import Settings

ACTIVE_STATUSES = ("queued", "running")
# 这些 Job 才会直接决定 ``EvalRun`` 的终态。归因任务附着在已完成的
# 评测记录之上，绝不能改写原评测状态。
RUN_EXECUTION_KINDS = ("evaluation", "resume", "rejudge", "cases_retry")


def reconcile_succeeded_run_statuses() -> int:
    """修复“持久化 Job 成功、Run 却仍为失败”的历史竞态。

    某些旧版本在 Web 服务重启窗口内可能先写入通用失败状态，而独立 Worker
    随后已经成功完成 Job。只以 *同一 run 最新的执行类 Job* 为准，且仅当
    该成功 Job 的完成时间不早于 Run 的失败时间时才回填；运行中、排队中及
    后续真正失败的任务都不会被触及。
    """
    repaired = 0
    with session_scope() as session:
        jobs = list(session.scalars(
            select(EvaluationJob)
            .where(EvaluationJob.kind.in_(RUN_EXECUTION_KINDS))
            .order_by(EvaluationJob.run_id, EvaluationJob.id.desc())
        ))
        latest_by_run: dict[int, EvaluationJob] = {}
        for job in jobs:
            latest_by_run.setdefault(job.run_id, job)

        for run_id, job in latest_by_run.items():
            if job.status != "succeeded" or job.finished_at is None:
                continue
            run = session.get(EvalRun, run_id)
            if run is None or run.status != "failed":
                continue
            # 若失败发生在成功 Job 之后，则它属于新的真实失败，不能覆盖。
            if run.finished_at is not None and job.finished_at < run.finished_at:
                continue
            run.status = "success"
            run.error_msg = ""
            run.finished_at = job.finished_at
            repaired += 1
    return repaired


def reconcile_unqueued_runs(settings: Settings) -> tuple[int, int]:
    """升级/异常窗口恢复：有断点的旧任务入队，无法重建的任务明确失败。"""
    recovered = 0
    failed = 0
    now = datetime.utcnow()
    with session_scope() as session:
        active_run_ids = set(
            session.scalars(
                select(EvaluationJob.run_id).where(
                    EvaluationJob.status.in_(ACTIVE_STATUSES)
                )
            )
        )
        runs = list(
            session.scalars(
                select(EvalRun).where(EvalRun.status.in_(("pending", "running")))
            )
        )
        for run in runs:
            if run.id in active_run_ids:
                continue
            try:
                out_dir = (
                    safe_join(settings.outputs_dir, run.run_slug)
                    if run.run_slug and run.run_slug != "(pending)"
                    else None
                )
            except ValueError:
                out_dir = None
            has_checkpoint = bool(
                out_dir is not None
                and any(
                    (out_dir / name).is_file()
                    for name in ("traces.partial.jsonl", "traces.jsonl.gz", "report.json")
                )
            )
            if has_checkpoint:
                session.add(
                    EvaluationJob(
                        run_id=run.id,
                        kind="resume",
                        payload={
                            "source_run_id": run.id,
                            "run_name": run.name,
                            "in_place": True,
                        },
                        status="queued",
                    )
                )
                run.status = "pending"
                run.finished_at = None
                run.error_msg = ""
                recovered += 1
                continue
            run.status = "failed"
            run.finished_at = now
            run.error_msg = "任务中断且缺少可恢复断点，请重新发起评测"
            failed += 1
    return recovered, failed


def enqueue_job(run_id: int, kind: str, payload: dict[str, Any]) -> int:
    """创建持久化任务；同一个 run 同时最多存在一个活跃任务。"""
    with session_scope() as session:
        existing = session.scalar(
            select(EvaluationJob)
            .where(
                EvaluationJob.run_id == run_id,
                EvaluationJob.status.in_(ACTIVE_STATUSES),
            )
            .order_by(EvaluationJob.id.desc())
        )
        if existing is not None:
            return existing.id
        row = EvaluationJob(run_id=run_id, kind=kind, payload=payload, status="queued")
        session.add(row)
        session.flush()
        return row.id


def enqueue_attribution_job(run_id: int, task_id: int) -> int:
    """为归因任务创建持久化 Worker Job。

    归因任务不能再依赖 Web 进程内的 ``asyncio.Task``：Web 发布或重启后，
    内存协程会消失，但逐 Case 的归因结果已经落库。这里按归因任务 ID 去重，
    使 Worker 可在租约过期或重启后从尚未成功的 Case 继续。
    """
    with session_scope() as session:
        active = list(session.scalars(
            select(EvaluationJob).where(
                EvaluationJob.run_id == run_id,
                EvaluationJob.kind == "attribution",
                EvaluationJob.status.in_(ACTIVE_STATUSES),
            )
        ))
        for row in active:
            if int((row.payload or {}).get("attribution_task_id") or 0) == task_id:
                return row.id
        row = EvaluationJob(
            run_id=run_id,
            kind="attribution",
            payload={"attribution_task_id": task_id},
            status="queued",
        )
        session.add(row)
        session.flush()
        return row.id


def cancel_attribution_job(task_id: int) -> bool:
    """取消指定归因任务的持久化 Job，而不影响同一评测的普通评测 Job。"""
    cancelled = False
    with session_scope() as session:
        rows = list(session.scalars(
            select(EvaluationJob).where(
                EvaluationJob.kind == "attribution",
                EvaluationJob.status.in_(ACTIVE_STATUSES),
            )
        ))
        for row in rows:
            if int((row.payload or {}).get("attribution_task_id") or 0) != task_id:
                continue
            row.status = "cancelled"
            row.finished_at = datetime.utcnow()
            row.lease_expires_at = None
            if row.lease_owner is None:
                row.heartbeat_at = datetime.utcnow()
            cancelled = True
    return cancelled


def claim_job(owner: str, lease_seconds: int) -> EvaluationJob | None:
    """领取最早的排队任务，或接管租约已过期的运行中任务。"""
    now = datetime.utcnow()
    expires = now + timedelta(seconds=max(10, lease_seconds))
    with session_scope() as session:
        stmt = (
            select(EvaluationJob)
            .where(
                or_(
                    EvaluationJob.status == "queued",
                    (
                        (EvaluationJob.status == "running")
                        & (EvaluationJob.lease_expires_at.is_not(None))
                        & (EvaluationJob.lease_expires_at < now)
                    ),
                )
            )
            .order_by(EvaluationJob.id)
            .limit(1)
        )
        # Postgres 用行锁跳过其他 Worker 已锁定的任务；SQLite 测试为单 Worker。
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        row = session.scalar(stmt)
        if row is None:
            return None
        row.status = "running"
        row.lease_owner = owner
        row.lease_expires_at = expires
        row.heartbeat_at = now
        row.attempts = int(row.attempts or 0) + 1
        if row.started_at is None:
            row.started_at = now
        row.error_msg = ""
        session.flush()
        session.expunge(row)
        return row


def heartbeat_job(
    job_id: int,
    owner: str,
    lease_seconds: int,
    *,
    progress: dict[str, Any] | None = None,
) -> bool:
    """续租并持久化进度；返回 False 表示任务被取消或租约已丢失。"""
    now = datetime.utcnow()
    with session_scope() as session:
        row = session.get(EvaluationJob, job_id)
        if row is None or row.status != "running" or row.lease_owner != owner:
            return False
        row.heartbeat_at = now
        row.lease_expires_at = now + timedelta(seconds=max(10, lease_seconds))
        if progress is not None:
            run = session.get(EvalRun, row.run_id)
            if run is not None:
                context = run.progress.get("context") if isinstance(run.progress, dict) else None
                run.progress = {
                    **progress,
                    **({"context": dict(context)} if isinstance(context, dict) else {}),
                }
        return True


def finish_job(job_id: int, owner: str, status: str, *, error: str = "") -> bool:
    if status not in {"succeeded", "failed", "cancelled"}:
        raise ValueError(f"非法任务终态: {status}")
    with session_scope() as session:
        row = session.get(EvaluationJob, job_id)
        if row is None or row.status != "running" or row.lease_owner != owner:
            return False
        row.status = status
        row.error_msg = error[:4000]
        row.finished_at = datetime.utcnow()
        row.lease_owner = None
        row.lease_expires_at = None
        # Job 已经无异常返回时，先在同一事务中把对应 Run 收敛为成功。这样即使
        # 随后 Web 服务重启或旧协程迟到，也不会出现“Job 成功、页面失败”的窗口。
        if status == "succeeded" and row.kind in RUN_EXECUTION_KINDS:
            run = session.get(EvalRun, row.run_id)
            if run is not None:
                run.status = "success"
                run.error_msg = ""
                run.finished_at = row.finished_at
        return True


def requeue_job(job_id: int, owner: str) -> bool:
    """Worker 正常退出时立即释放租约，让新实例无需等待超时即可恢复。"""
    with session_scope() as session:
        row = session.get(EvaluationJob, job_id)
        if row is None or row.status != "running" or row.lease_owner != owner:
            return False
        row.status = "queued"
        row.lease_owner = None
        row.lease_expires_at = None
        row.heartbeat_at = datetime.utcnow()
        # 归因是评测完成后的附属任务，不能把原评测 Run 回写为 pending。
        if row.kind != "attribution":
            run = session.get(EvalRun, row.run_id)
            if run is not None and run.status not in {"success", "failed"}:
                run.status = "pending"
                run.error_msg = ""
                run.finished_at = None
        return True


def cancel_job(run_id: int) -> bool:
    with session_scope() as session:
        row = session.scalar(
            select(EvaluationJob)
            .where(
                EvaluationJob.run_id == run_id,
                EvaluationJob.status.in_(ACTIVE_STATUSES),
            )
            .order_by(EvaluationJob.id.desc())
        )
        if row is None:
            return False
        row.status = "cancelled"
        row.finished_at = datetime.utcnow()
        row.lease_expires_at = None
        if row.lease_owner is None:
            row.heartbeat_at = datetime.utcnow()
        return True


def acknowledge_cancel(job_id: int, owner: str) -> bool:
    with session_scope() as session:
        row = session.get(EvaluationJob, job_id)
        if row is None or row.status != "cancelled" or row.lease_owner != owner:
            return False
        row.lease_owner = None
        row.heartbeat_at = datetime.utcnow()
        return True


def job_is_executing(run_id: int) -> bool:
    with session_scope() as session:
        row = session.scalar(
            select(EvaluationJob)
            .where(EvaluationJob.run_id == run_id)
            .order_by(EvaluationJob.id.desc())
        )
        return bool(row is not None and row.lease_owner)


def progress_snapshot(run_id: int) -> dict[str, Any] | None:
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        return dict(run.progress or {}) if run is not None and run.progress else None


def queue_snapshot(run_id: int) -> dict[str, Any] | None:
    with session_scope() as session:
        row = session.scalar(
            select(EvaluationJob)
            .where(EvaluationJob.run_id == run_id)
            .order_by(EvaluationJob.id.desc())
        )
        if row is None or row.status not in ACTIVE_STATUSES:
            return None
        if row.status == "running":
            return {"state": "running", "position": 0}
        ahead = session.scalar(
            select(func.count(EvaluationJob.id)).where(
                EvaluationJob.status == "queued",
                EvaluationJob.id <= row.id,
            )
        )
        return {"state": "queued", "position": int(ahead or 1)}


def active_job_count() -> int:
    with session_scope() as session:
        return int(
            session.scalar(
                select(func.count(EvaluationJob.id)).where(
                    EvaluationJob.status.in_(ACTIVE_STATUSES)
                )
            )
            or 0
        )


def job_status(job_id: int) -> str | None:
    with session_scope() as session:
        row = session.get(EvaluationJob, job_id)
        return row.status if row is not None else None
