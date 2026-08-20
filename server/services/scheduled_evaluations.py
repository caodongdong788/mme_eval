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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import session_scope
from ..jobs import commit_and_submit_job, get_job_runner
from ..models_db import (
    AttributionTask,
    AttributionTaskItem,
    Benchmark,
    CaseResultRow,
    EvalRun,
    JudgeModelConfig,
    ScheduledEvaluation,
)
from ..schemas import AdapterOverride, JudgeOverride, RunCreate, ScheduledEvaluationCreate, ScheduledEvaluationUpdate
from ..settings import Settings, get_settings
from . import runs as runs_svc

logger = logging.getLogger("mme.scheduled-evaluations")
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_SCHEDULE_RETRY_DELAY = timedelta(minutes=5)
_scheduler_task: asyncio.Task | None = None
_AUTO_ATTRIBUTION_GRADE = "不合格"


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
    if (
        payload.auto_attribution_enabled
        and session.get(JudgeModelConfig, payload.auto_attribution_model_id) is None
    ):
        raise HTTPException(status_code=404, detail="自动归因所选模型不存在")


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
    """发起所有到点任务；Run、队列任务与 next_run_at 在同一事务提交。"""
    due_occurrences: list[tuple[int, str]] = []
    now = _utc_now()
    with session_scope() as session:
        stmt = select(ScheduledEvaluation).where(
                    ScheduledEvaluation.enabled.is_(True),
                    ScheduledEvaluation.next_run_at.is_not(None),
                    ScheduledEvaluation.next_run_at <= now,
                )
        due = list(session.scalars(stmt))
        for task in due:
            occurrence_key = (
                f"{task.id}:{task.next_run_at.isoformat(timespec='microseconds')}"
            )
            due_occurrences.append((task.id, occurrence_key))

    created = 0
    for task_id, occurrence_key in due_occurrences:
        try:
            plan = await launch_scheduled_evaluation(
                task_id,
                now=now,
                require_enabled=True,
                occurrence_key=occurrence_key,
            )
            if plan is None:
                continue
            created += 1
        except Exception as exc:  # noqa: BLE001 - 单个任务失败不阻塞其他定时任务
            logger.exception("定时评测任务 #%s 触发失败", task_id)
            with session_scope() as session:
                task = session.get(ScheduledEvaluation, task_id)
                if task is not None:
                    task.last_error = str(exc)[:1000]
                    # 本次触发失败不应直接跳到下一天/下周；5 分钟后补偿重试，
                    # 同时避免外部服务持续异常时每 20 秒热循环。
                    task.next_run_at = _utc_now() + _SCHEDULE_RETRY_DELAY
    return created


async def launch_scheduled_evaluation(
    task_id: int,
    *,
    now: datetime | None = None,
    require_enabled: bool = False,
    occurrence_key: str | None = None,
):
    """按既定定时任务参数立刻创建一次回归 run。

    手动点击“立即执行”与调度器到点执行共用这一入口，均绑定
    ``scheduled_evaluation_id`` 和 ``trigger_type=scheduled``，确保回归趋势可连续分析。
    """
    triggered_at = _utc_now(now)
    # DeepTrace 是外部网络 IO，必须在开启事务、尤其是 PostgreSQL FOR UPDATE
    # 之前完成，避免最慢 8 秒的远端等待长期占用连接和定时任务行锁。
    version_name = await fetch_latest_active_deeptrace_version_name()
    try:
        with session_scope() as session:
            task_stmt = select(ScheduledEvaluation).where(
                ScheduledEvaluation.id == task_id
            )
            if occurrence_key and session.bind is not None and session.bind.dialect.name == "postgresql":
                task_stmt = task_stmt.with_for_update()
            task = session.scalar(task_stmt)
            if task is None:
                raise HTTPException(status_code=404, detail=f"定时评测任务 {task_id} 不存在")
            if require_enabled and not task.enabled:
                return None
            if occurrence_key and session.scalar(
                select(EvalRun.id).where(
                    EvalRun.scheduled_evaluation_id == task_id,
                    EvalRun.scheduled_occurrence_key == occurrence_key,
                )
            ):
                return None
            timestamp = triggered_at.replace(tzinfo=timezone.utc).astimezone(_SHANGHAI).strftime("%Y%m%d-%H%M%S")
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
                    task.user_simulator_model_id if task.evaluation_mode == "multi_turn" else None
                ),
            )
            plan = runs_svc.prepare_create_run(
                session,
                run_payload,
                created_by=task.created_by or "定时任务",
                trigger_type="scheduled",
                scheduled_evaluation_id=task.id,
                scheduled_occurrence_key=occurrence_key,
            )
            # 流式归因任务必须在评测 Job 可见之前创建，否则队列 Worker 可能先
            # 完成首条 Case，导致这条不合格结果没有可追加的归因任务。
            try:
                _prepare_configured_streaming_attribution_in_session(session, plan.run, task)
            except Exception:  # noqa: BLE001 - 归因预建失败不应阻断定时评测
                logger.exception(
                    "run #%s 预创建流水线归因任务失败，将在评测完成后补偿",
                    plan.run.id,
                )
            task.last_run_at = triggered_at
            task.last_error = ""
            if occurrence_key:
                # 与 EvalRun / EvaluationJob 一起提交。进程若在提交前崩溃，时间不
                # 会被提前推进，下一轮调度仍会重试同一 occurrence。
                task.next_run_at = compute_next_run_at(task, triggered_at)

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
                judge_model_id=getattr(plan, "judge_model_id", None),
                user_simulator_model_id=getattr(plan, "user_simulator_model_id", None),
            )
            await commit_and_submit_job(
                session,
                plan.run.id,
                job,
                job_runner=get_job_runner(),
                failure_message="定时任务提交执行队列失败",
            )
    except IntegrityError:
        if occurrence_key:
            # 只吞掉 occurrence 唯一约束竞争；其他完整性错误仍需进入补偿重试。
            with session_scope() as verify_session:
                exists = verify_session.scalar(
                    select(EvalRun.id).where(
                        EvalRun.scheduled_evaluation_id == task_id,
                        EvalRun.scheduled_occurrence_key == occurrence_key,
                    )
                )
            if exists:
                return None
        raise

    return plan


def _uses_distinct_attribution_model(schedule: ScheduledEvaluation) -> bool:
    return bool(
        schedule.auto_attribution_enabled
        and schedule.enable_judge
        and schedule.judge_model_id
        and schedule.auto_attribution_model_id
        and schedule.judge_model_id != schedule.auto_attribution_model_id
    )


def _prepare_configured_streaming_attribution_in_session(
    session: Session,
    run: EvalRun,
    schedule: ScheduledEvaluation,
) -> int | None:
    """在调用方事务内预建流式归因任务，保证它先于评测 Job 一起提交。"""
    from . import attribution_tasks

    if run.trigger_type != "scheduled" or not _uses_distinct_attribution_model(schedule):
        return None
    existing = session.scalar(
        select(AttributionTask).where(
            AttributionTask.run_id == run.id,
            AttributionTask.is_streaming.is_(True),
        ).order_by(AttributionTask.id.desc())
    )
    if existing is not None:
        return existing.id
    task = attribution_tasks.create_streaming_attribution_task(
        session,
        run,
        judge_model_id=int(schedule.auto_attribution_model_id),
        created_by=schedule.created_by or "定时任务自动归因",
    )
    return task.id


def prepare_configured_streaming_attribution(run_id: int) -> int | None:
    """为满足条件的定时评测预建唯一的、不合格 Case 流水线归因任务。"""
    try:
        with session_scope() as session:
            run = session.get(EvalRun, run_id)
            if run is None or run.trigger_type != "scheduled" or not run.scheduled_evaluation_id:
                return None
            schedule = session.get(ScheduledEvaluation, run.scheduled_evaluation_id)
            if schedule is None:
                return None
            return _prepare_configured_streaming_attribution_in_session(session, run, schedule)
    except Exception:  # noqa: BLE001 - 归因预建失败不应阻断定时评测
        logger.exception("run #%s 预创建流水线归因任务失败，将在评测完成后补偿", run_id)
        return None


def get_open_streaming_attribution_task_id(run_id: int) -> int | None:
    """返回仍在接收 Case 的流水线归因任务，供评测断点恢复后继续追加。"""
    with session_scope() as session:
        return session.scalar(
            select(AttributionTask.id)
            .where(
                AttributionTask.run_id == run_id,
                AttributionTask.is_streaming.is_(True),
                AttributionTask.intake_open.is_(True),
            )
            .order_by(AttributionTask.id.desc())
        )


async def append_configured_streaming_attribution_case(run_id: int, sample_id: str) -> bool:
    """评测完成一条后，仅把最终综合评价为“不合格”的 Case 追加进归因任务。"""
    from . import attribution_tasks

    task_id: int | None = None
    try:
        with session_scope() as session:
            row = session.scalar(
                select(CaseResultRow).where(
                    CaseResultRow.run_id == run_id,
                    CaseResultRow.sample_id == sample_id,
                )
            )
            if row is None or row.grade != _AUTO_ATTRIBUTION_GRADE:
                return False
            task = session.scalar(
                select(AttributionTask)
                .where(
                    AttributionTask.run_id == run_id,
                    AttributionTask.is_streaming.is_(True),
                    AttributionTask.intake_open.is_(True),
                )
                .order_by(AttributionTask.id.desc())
            )
            if task is None:
                return False
            if not attribution_tasks.append_streaming_attribution_item(
                session, task, sample_id=sample_id
            ):
                return False
            task_id = task.id
    except Exception:  # noqa: BLE001 - 单条归因入队失败不能影响评测结果
        logger.exception("run #%s Case %s 追加流水线归因失败", run_id, sample_id)
        return False

    if task_id is not None:
        try:
            attribution_tasks.start_attribution_task(task_id)
        except Exception:  # noqa: BLE001 - 保留 pending 明细，整批完成时会补提交
            logger.exception("run #%s 流水线归因任务 #%s 启动失败", run_id, task_id)
            return False
    return True


def abort_configured_streaming_attribution(run_id: int, reason: str) -> None:
    """评测不可恢复地失败时关闭仍在等待新 Case 的归因任务。"""
    with session_scope() as session:
        task = session.scalar(
            select(AttributionTask)
            .where(
                AttributionTask.run_id == run_id,
                AttributionTask.is_streaming.is_(True),
                AttributionTask.intake_open.is_(True),
            )
            .order_by(AttributionTask.id.desc())
        )
        if task is None:
            return
        task.intake_open = False
        if task.status in {"queued", "running"} and task.completed_count >= task.total_count:
            task.status = "failed"
            task.error_msg = reason[:2000]
            task.finished_at = datetime.utcnow()


async def start_configured_attribution(run_id: int) -> int | None:
    """按定时任务配置为本次已完成评测自动创建归因任务。

    自动归因只处理综合评价为“不合格”的 Case。不同模型的定时任务在评测期间
    已逐条追加，此处负责关闭接收并补提交；相同模型则在整批完成后一次性创建。
    """
    from . import attribution_tasks

    attribution_task_id: int | None = None
    try:
        with session_scope() as session:
            run = session.get(EvalRun, run_id)
            if run is None or run.trigger_type != "scheduled" or not run.scheduled_evaluation_id:
                return None
            schedule = session.get(ScheduledEvaluation, run.scheduled_evaluation_id)
            if schedule is None or not schedule.auto_attribution_enabled:
                return None

            if not schedule.auto_attribution_model_id:
                logger.warning("定时任务 #%s 自动归因配置无效，已跳过", schedule.id)
                return None
            streaming = session.scalar(
                select(AttributionTask)
                .where(
                    AttributionTask.run_id == run.id,
                    AttributionTask.is_streaming.is_(True),
                )
                .order_by(AttributionTask.id.desc())
            )
            if streaming is not None:
                # 最终 report 会再次 upsert Case 明细；把流水线阶段已经完成的归因
                # 快照恢复回 CaseResult，保证旧的单 Case 归因读取接口仍然可用。
                attribution_tasks.restore_streaming_attribution_snapshots(session, streaming)
                attribution_tasks.close_streaming_attribution_task(session, streaming)
                attribution_task_id = streaming.id
                should_start = bool(session.scalar(
                    select(AttributionTaskItem.id).where(
                        AttributionTaskItem.task_id == streaming.id,
                        AttributionTaskItem.status == "pending",
                    ).limit(1)
                ))
                if not should_start:
                    return attribution_task_id
            else:
                sample_ids = list(session.scalars(
                    select(CaseResultRow.sample_id)
                    .where(
                        CaseResultRow.run_id == run.id,
                        CaseResultRow.grade == _AUTO_ATTRIBUTION_GRADE,
                    )
                    .order_by(CaseResultRow.sample_id)
                ))
                if not sample_ids:
                    logger.info("定时任务 #%s 本次无不合格 Case，已跳过自动归因", schedule.id)
                    return None
                task = attribution_tasks.create_attribution_task(
                    session,
                    run,
                    sample_ids=sample_ids,
                    judge_model_id=schedule.auto_attribution_model_id,
                    created_by=schedule.created_by or "定时任务自动归因",
                    include_passed=False,
                )
                attribution_task_id = task.id
    except Exception:  # noqa: BLE001 - 自动归因不得将已成功评测标为失败
        logger.exception("run #%s 自动创建归因任务失败", run_id)
        abort_configured_streaming_attribution(run_id, "定时评测完成，但自动归因收尾失败")
        return None

    if attribution_task_id is not None:
        try:
            attribution_tasks.start_attribution_task(attribution_task_id)
        except Exception:  # noqa: BLE001 - 保留已创建任务，方便人工恢复
            logger.exception("run #%s 自动归因任务 #%s 启动失败", run_id, attribution_task_id)
            attribution_tasks.mark_attribution_task_start_failed(
                attribution_task_id, RuntimeError("自动归因任务提交失败")
            )
            return None
    return attribution_task_id


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
