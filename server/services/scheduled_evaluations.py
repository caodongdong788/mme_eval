"""周期性评测任务的配置和触发器。"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import session_scope
from ..jobs import get_job_runner
from ..models_db import Benchmark, ScheduledEvaluation
from ..schemas import AdapterOverride, JudgeOverride, RunCreate, ScheduledEvaluationCreate, ScheduledEvaluationUpdate
from ..settings import Settings, get_settings
from . import runs as runs_svc

logger = logging.getLogger("mme.scheduled-evaluations")
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_scheduler_task: asyncio.Task | None = None


def _version_items(payload: object) -> list[dict]:
    """兼容 DeepTrace 常见的分页包装和直接数组返回。"""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("items", "data", "versions", "list", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _version_items(value)
            if nested:
                return nested
    return [payload] if "name" in payload else []


async def fetch_latest_active_deeptrace_version_name(
    settings: Settings | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    """读取 DeepTrace 第一页 active 版本的 name；不可用时降级为无版本后缀。"""
    settings = settings or get_settings()
    token = settings.deeptrace_open_api_token.strip()
    space_key = settings.deeptrace_space_key.strip()
    if not token or not space_key:
        return None
    url = f"{settings.deeptrace_base_url}/api/open/v1/spaces/{space_key}/versions"
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.deeptrace_timeout_seconds)
    try:
        response = await client.get(
            url,
            params={"status": "active", "page": 1, "pageSize": 50},
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        versions = _version_items(response.json())
        for version in versions:
            name = str(version.get("name") or "").strip()
            if name:
                return name
    except (httpx.HTTPError, ValueError):
        logger.warning("读取 DeepTrace active 版本失败，将不追加版本名称", exc_info=True)
    finally:
        if owns_client:
            await client.aclose()
    return None


def _utc_now(now: Optional[datetime] = None) -> datetime:
    """数据库统一存 UTC naive，和平台其余时间字段保持一致。"""
    if now is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    return now.astimezone(timezone.utc).replace(tzinfo=None) if now.tzinfo else now


def compute_next_run_at(task: ScheduledEvaluation, now: Optional[datetime] = None) -> datetime:
    """计算严格晚于当前时刻的下一次执行时间（上海时区、数据库保存无时区本地时间）。"""
    current_utc = _utc_now(now)
    current = current_utc.replace(tzinfo=timezone.utc).astimezone(_SHANGHAI)
    hour, minute = (int(part) for part in task.schedule_time.split(":"))
    if task.schedule_kind == "daily":
        candidate = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
        target = candidate if candidate > current else candidate + timedelta(days=1)
        return target.astimezone(timezone.utc).replace(tzinfo=None)

    weekdays = sorted({int(day) for day in (task.weekdays or []) if 0 <= int(day) <= 6})
    if not weekdays:
        # 防御历史脏数据；前端/Schema 均不允许这种配置。
        weekdays = [current.weekday()]
    for delta in range(8):
        candidate = (current + timedelta(days=delta)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        if candidate.weekday() in weekdays and candidate > current:
            return candidate.astimezone(timezone.utc).replace(tzinfo=None)
    return (current + timedelta(days=7)).astimezone(timezone.utc).replace(tzinfo=None)


def _get_or_404(session: Session, task_id: int) -> ScheduledEvaluation:
    task = session.get(ScheduledEvaluation, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"定时任务 {task_id} 不存在")
    return task


def _validate_references(session: Session, payload: ScheduledEvaluationCreate) -> None:
    if session.get(Benchmark, payload.benchmark_id) is None:
        raise HTTPException(status_code=404, detail=f"benchmark {payload.benchmark_id} 不存在")


def list_scheduled_evaluations(session: Session) -> list[ScheduledEvaluation]:
    return list(session.scalars(select(ScheduledEvaluation).order_by(ScheduledEvaluation.id.desc())))


def create_scheduled_evaluation(
    session: Session, payload: ScheduledEvaluationCreate, *, created_by: str | None
) -> ScheduledEvaluation:
    _validate_references(session, payload)
    task = ScheduledEvaluation(**payload.model_dump(), created_by=created_by)
    task.next_run_at = compute_next_run_at(task)
    session.add(task)
    try:
        session.commit()
    except Exception as exc:
        session.rollback()
        if "unique" in str(exc).lower():
            raise HTTPException(status_code=409, detail=f"定时任务名称「{payload.name}」已存在") from exc
        raise
    session.refresh(task)
    return task


def update_scheduled_evaluation(
    session: Session, task_id: int, payload: ScheduledEvaluationUpdate
) -> ScheduledEvaluation:
    task = _get_or_404(session, task_id)
    raw = {field: getattr(task, field) for field in ScheduledEvaluationCreate.model_fields}
    raw.update(payload.model_dump(exclude_unset=True))
    try:
        validated = ScheduledEvaluationCreate(**raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _validate_references(session, validated)
    for key, value in validated.model_dump().items():
        setattr(task, key, value)
    task.next_run_at = compute_next_run_at(task)
    task.last_error = ""
    try:
        session.commit()
    except Exception as exc:
        session.rollback()
        if "unique" in str(exc).lower():
            raise HTTPException(status_code=409, detail=f"定时任务名称「{validated.name}」已存在") from exc
        raise
    session.refresh(task)
    return task


def delete_scheduled_evaluation(session: Session, task_id: int) -> None:
    session.delete(_get_or_404(session, task_id))
    session.commit()


async def run_due_scheduled_evaluations_once() -> int:
    """发起所有到点的任务；先推进 next_run_at，避免执行较慢时重复提交。"""
    due_ids: list[int] = []
    now = _utc_now()
    with session_scope() as session:
        due = list(
            session.scalars(
                select(ScheduledEvaluation).where(
                    ScheduledEvaluation.enabled.is_(True),
                    ScheduledEvaluation.next_run_at.is_not(None),
                    ScheduledEvaluation.next_run_at <= now,
                )
            )
        )
        for task in due:
            task.next_run_at = compute_next_run_at(task, now)
            due_ids.append(task.id)

    created = 0
    for task_id in due_ids:
        try:
            with session_scope() as session:
                task = session.get(ScheduledEvaluation, task_id)
                if task is None or not task.enabled:
                    continue
                timestamp = now.replace(tzinfo=timezone.utc).astimezone(_SHANGHAI).strftime("%Y%m%d-%H%M%S")
                version_name = await fetch_latest_active_deeptrace_version_name()
                run_name_parts = [task.name]
                if version_name:
                    run_name_parts.append(version_name)
                run_name_parts.append(f"定时 {timestamp}")
                run_payload = RunCreate(
                    benchmark_id=task.benchmark_id,
                    run_name=" · ".join(run_name_parts),
                    evaluation_mode=task.evaluation_mode,
                    levels=task.levels or [],
                    limit=task.limit,
                    repeat=task.repeat,
                    judge=JudgeOverride(enabled=task.enable_judge),
                    adapter=AdapterOverride(enable_rag=task.enable_rag),
                    judge_model_id=task.judge_model_id,
                    user_simulator_model_id=(
                        task.user_simulator_model_id
                        if task.evaluation_mode == "multi_turn"
                        else None
                    ),
                )
                plan = runs_svc.prepare_create_run(
                    session,
                    run_payload,
                    created_by=task.created_by or "定时任务",
                    trigger_type="scheduled",
                    scheduled_evaluation_id=task.id,
                )
                task.last_run_at = now
                task.last_error = ""

            from ..routers.runs import build_eval_job

            job = build_eval_job(
                plan.run.id,
                benchmark_id=plan.benchmark_id,
                run_name=plan.run_name,
                levels=plan.levels,
                limit=plan.limit,
                repeat=plan.repeat,
                judge_full=plan.judge_full,
                adapter_full=plan.adapter_full,
            )
            await get_job_runner().submit(plan.run.id, job)
            created += 1
        except Exception as exc:  # noqa: BLE001 - 单个任务失败不阻塞其他定时任务
            logger.exception("定时评测任务 #%s 触发失败", task_id)
            with session_scope() as session:
                task = session.get(ScheduledEvaluation, task_id)
                if task is not None:
                    task.last_error = str(exc)[:1000]
    return created


async def _scheduler_loop() -> None:
    while True:
        try:
            count = await run_due_scheduled_evaluations_once()
            if count:
                logger.info("已触发 %s 条定时评测", count)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("定时评测调度循环异常")
        await asyncio.sleep(20)


def start_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop(), name="mme-scheduled-evaluations")


async def stop_scheduler() -> None:
    global _scheduler_task
    task, _scheduler_task = _scheduler_task, None
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
