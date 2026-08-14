"""批量 AI 归因任务：最多同时分析 3 个不合格 Case，并逐条落库。"""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any

from fastapi import HTTPException
import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import session_scope
from ..models_db import (
    AttributionTask,
    AttributionTaskItem,
    CaseResultRow,
    EvalRun,
    JudgeModelConfig,
)
from .case_attribution import generate_case_attribution
from .case_query import case_row_or_404
from .attribution_summary import build_task_diagnostic_summary
from .judge_models import get_judge_model_or_404, has_judge_model_api_key


log = logging.getLogger(__name__)
_MAX_CONCURRENCY = 3
_task_futures: dict[int, asyncio.Task] = {}
_global_semaphore: asyncio.Semaphore | None = None


def _semaphore() -> asyncio.Semaphore:
    global _global_semaphore
    if _global_semaphore is None:
        _global_semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
    return _global_semaphore


def _task_out(session: Session, task: AttributionTask, *, include_items: bool) -> dict[str, Any]:
    running_count = 0
    if task.status in {"queued", "running"}:
        running_count = int(session.scalar(
            select(func.count(AttributionTaskItem.id)).where(
                AttributionTaskItem.task_id == task.id,
                AttributionTaskItem.status == "running",
            )
        ) or 0)
    pending_count = max(0, task.total_count - task.completed_count - running_count)
    output = {
        "id": task.id,
        "run_id": task.run_id,
        "judge_model_id": task.judge_model_id,
        "judge_model_name": task.judge_model_name,
        "status": task.status,
        "requested_count": task.requested_count,
        "total_count": task.total_count,
        "skipped_count": task.skipped_count,
        "completed_count": task.completed_count,
        "success_count": task.success_count,
        "failed_count": task.failed_count,
        "running_count": running_count,
        "pending_count": pending_count,
        "error_msg": task.error_msg,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "diagnostic_summary": {},
        "items": [],
    }
    if not include_items:
        return output
    rows = list(session.scalars(
        select(AttributionTaskItem)
        .where(AttributionTaskItem.task_id == task.id)
        .order_by(AttributionTaskItem.id)
    ))
    output["diagnostic_summary"] = build_task_diagnostic_summary(
        (item.sample_id, item.analysis_json) for item in rows
    )
    case_rows = {
        row.sample_id: row
        for row in session.scalars(
            select(CaseResultRow).where(
                CaseResultRow.run_id == task.run_id,
                CaseResultRow.sample_id.in_([item.sample_id for item in rows]),
            )
        )
    }
    output["items"] = [
        {
            "sample_id": item.sample_id,
            "scenario": case_rows.get(item.sample_id).scenario if case_rows.get(item.sample_id) else "",
            "case_type": case_rows.get(item.sample_id).case_type if case_rows.get(item.sample_id) else "",
            "status": item.status,
            "error_msg": item.error_msg,
            "attribution_available": bool(
                isinstance(item.analysis_json, dict) and item.analysis_json.get("available")
            ),
            "attribution_stale": bool(
                isinstance(item.analysis_json, dict) and item.analysis_json.get("stale")
            ),
            "started_at": item.started_at,
            "finished_at": item.finished_at,
        }
        for item in rows
    ]
    return output


def list_attribution_tasks(session: Session, run_id: int) -> list[dict[str, Any]]:
    tasks = list(session.scalars(
        select(AttributionTask)
        .where(AttributionTask.run_id == run_id)
        .order_by(AttributionTask.id.desc())
    ))
    return [_task_out(session, task, include_items=False) for task in tasks]


def get_attribution_task_or_404(session: Session, run_id: int, task_id: int) -> AttributionTask:
    task = session.get(AttributionTask, task_id)
    if task is None or task.run_id != run_id:
        raise HTTPException(status_code=404, detail=f"归因任务 {task_id} 不存在")
    return task


def get_attribution_task(session: Session, run_id: int, task_id: int) -> dict[str, Any]:
    return _task_out(session, get_attribution_task_or_404(session, run_id, task_id), include_items=True)


def get_attribution_task_item_result(
    session: Session, run_id: int, task_id: int, sample_id: str
) -> dict[str, Any]:
    task = get_attribution_task_or_404(session, run_id, task_id)
    item = session.scalar(
        select(AttributionTaskItem).where(
            AttributionTaskItem.task_id == task.id,
            AttributionTaskItem.sample_id == sample_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail=f"归因任务中不存在用例 {sample_id}")
    if not isinstance(item.analysis_json, dict) or not item.analysis_json.get("available"):
        raise HTTPException(status_code=404, detail="该用例尚无本次任务的归因结果")
    return item.analysis_json


def create_attribution_task(
    session: Session,
    run: EvalRun,
    *,
    sample_ids: list[str],
    judge_model_id: int,
    created_by: str | None,
) -> AttributionTask:
    active = session.scalar(
        select(AttributionTask.id).where(
            AttributionTask.run_id == run.id,
            AttributionTask.status.in_(("queued", "running")),
        )
    )
    if active is not None:
        raise HTTPException(status_code=409, detail="该评测已有进行中的归因任务，请等待完成后再发起")
    model = get_judge_model_or_404(session, judge_model_id)
    if not has_judge_model_api_key(model):
        raise HTTPException(status_code=422, detail=f"归因模型「{model.name}」未配置可用的 API Key")
    ordered_ids = list(dict.fromkeys(item.strip() for item in sample_ids if item.strip()))
    if not ordered_ids:
        raise HTTPException(status_code=422, detail="请至少选择一个用例")
    rows = list(session.scalars(
        select(CaseResultRow).where(
            CaseResultRow.run_id == run.id,
            CaseResultRow.sample_id.in_(ordered_ids),
        )
    ))
    by_sample = {row.sample_id: row for row in rows}
    unknown = [sample_id for sample_id in ordered_ids if sample_id not in by_sample]
    if unknown:
        raise HTTPException(status_code=422, detail=f"存在不属于当前评测的用例：{unknown[0]}")
    failed_ids = [sample_id for sample_id in ordered_ids if not by_sample[sample_id].release_passed]
    if not failed_ids:
        raise HTTPException(status_code=422, detail="当前筛选结果没有不合格用例可归因")
    task = AttributionTask(
        run_id=run.id,
        judge_model_id=model.id,
        judge_model_name=model.name,
        status="queued",
        requested_count=len(ordered_ids),
        total_count=len(failed_ids),
        skipped_count=len(ordered_ids) - len(failed_ids),
        created_by=created_by,
    )
    session.add(task)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="该评测已有进行中的归因任务，请等待完成后再发起",
        ) from exc
    session.add_all(AttributionTaskItem(task_id=task.id, sample_id=sample_id) for sample_id in failed_ids)
    session.flush()
    return task


def resume_attribution_task(
    session: Session, run_id: int, task_id: int
) -> AttributionTask:
    """在原任务中继续归因，只重新排队未成功完成的 Case。

    服务重启或模型调用异常后，已成功写入 ``analysis_json`` 的条目不可被覆盖；
    仅把 pending/running/failed 条目恢复为 pending，由后续 worker 按原模型继续处理。
    """
    task = get_attribution_task_or_404(session, run_id, task_id)
    if task.status in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="该归因任务正在执行，无需继续归因")
    other_active = session.scalar(
        select(AttributionTask.id).where(
            AttributionTask.run_id == run_id,
            AttributionTask.id != task.id,
            AttributionTask.status.in_(("queued", "running")),
        )
    )
    if other_active is not None:
        raise HTTPException(status_code=409, detail="该评测已有其他进行中的归因任务")

    items = list(session.scalars(
        select(AttributionTaskItem)
        .where(
            AttributionTaskItem.task_id == task.id,
            AttributionTaskItem.status != "success",
        )
        .order_by(AttributionTaskItem.id)
    ))
    if not items:
        raise HTTPException(status_code=422, detail="该归因任务已全部完成，无需继续归因")

    for item in items:
        item.status = "pending"
        item.error_msg = ""
        item.started_at = None
        item.finished_at = None
        # 失败项通常没有结果；若存在不完整结果也不能作为本轮可查看归因。
        if not isinstance(item.analysis_json, dict) or not item.analysis_json.get("available"):
            item.analysis_json = None

    task.status = "queued"
    task.error_msg = ""
    task.finished_at = None
    try:
        session.flush()
        _refresh_task_counts(session, task)
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="该评测已有其他进行中的归因任务") from exc
    return task


def _refresh_task_counts(session: Session, task: AttributionTask) -> None:
    counts = dict(session.execute(
        select(AttributionTaskItem.status, func.count(AttributionTaskItem.id))
        .where(AttributionTaskItem.task_id == task.id)
        .group_by(AttributionTaskItem.status)
    ).all())
    task.success_count = int(counts.get("success", 0))
    task.failed_count = int(counts.get("failed", 0))
    task.completed_count = task.success_count + task.failed_count
    if task.completed_count < task.total_count:
        return
    task.finished_at = datetime.utcnow()
    if task.failed_count == 0:
        task.status = "success"
    elif task.success_count == 0:
        task.status = "failed"
    else:
        task.status = "partial"


def _set_task_running(task_id: int) -> None:
    with session_scope() as session:
        task = session.get(AttributionTask, task_id)
        if task is None:
            return
        task.status = "running"
        task.started_at = task.started_at or datetime.utcnow()


async def _run_item(task_id: int, item_id: int) -> None:
    try:
        async with _semaphore():
            # 先用一个短事务落下“分析中”，避免在等待模型响应期间持有 SQLite 写锁。
            with session_scope() as session:
                item = session.get(AttributionTaskItem, item_id)
                if item is None:
                    return
                item.status = "running"
                item.started_at = datetime.utcnow()

            with session_scope() as session:
                task = session.get(AttributionTask, task_id)
                item = session.get(AttributionTaskItem, item_id)
                if task is None or item is None:
                    return
                run = session.get(EvalRun, task.run_id)
                if run is None:
                    raise RuntimeError("评测运行不存在")
                row = case_row_or_404(session, run.id, item.sample_id)
                result = await generate_case_attribution(
                    session,
                    run,
                    row,
                    judge_model_id=task.judge_model_id,
                    attribution_task_id=task.id,
                    attribution_item_id=item.id,
                )
                item.analysis_json = result
                item.status = "success"
                item.finished_at = datetime.utcnow()
                _refresh_task_counts(session, task)
    except Exception as exc:  # noqa: BLE001 - 每个 Case 独立失败，整批继续
        log.exception("attribution task=%s item=%s failed", task_id, item_id)
        with session_scope() as session:
            task = session.get(AttributionTask, task_id)
            item = session.get(AttributionTaskItem, item_id)
            if task is None or item is None:
                return
            item.status = "failed"
            item.error_msg = f"{type(exc).__name__}: {exc}"[:1000]
            item.finished_at = datetime.utcnow()
            _refresh_task_counts(session, task)


async def run_attribution_task(task_id: int) -> None:
    _set_task_running(task_id)
    with session_scope() as session:
        item_ids = list(session.scalars(
            select(AttributionTaskItem.id)
            .where(
                AttributionTaskItem.task_id == task_id,
                AttributionTaskItem.status == "pending",
            )
            .order_by(AttributionTaskItem.id)
        ))
    try:
        await asyncio.gather(*(_run_item(task_id, item_id) for item_id in item_ids))
    finally:
        _task_futures.pop(task_id, None)


def start_attribution_task(task_id: int) -> None:
    _task_futures[task_id] = asyncio.create_task(
        run_attribution_task(task_id), name=f"mme-attribution-{task_id}"
    )


async def cancel_attribution_task(task_id: int) -> None:
    future = _task_futures.get(task_id)
    if future is None or future.done():
        return
    future.cancel()
    try:
        await future
    except (asyncio.CancelledError, Exception):
        pass
    finally:
        _task_futures.pop(task_id, None)


def _codex_cancel_url(base_url: str) -> str:
    """将 OpenAI 兼容 base URL 转换为本机 Codex 网关的取消接口。"""
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        normalized = normalized[:-3]
    return f"{normalized}/attribution/cancel"


async def _cancel_codex_gateway_task(session: Session, task: AttributionTask) -> None:
    """请求本机 Codex 网关终止属于归因任务的 CLI 子进程。

    非 Codex 模型没有可控的本地子进程，仍由取消本服务协程来中断 HTTP 请求。
    网关把已取消任务记住，因此即使请求正处在建立阶段，也不会在删除后继续启动。
    """
    model = session.get(JudgeModelConfig, task.judge_model_id)
    if model is None or (model.provider or "").strip().lower() != "codex":
        return
    if not (model.base_url or "").strip() or not (model.api_key or "").strip():
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                _codex_cancel_url(model.base_url),
                headers={"Authorization": f"Bearer {model.api_key}"},
                json={"task_id": task.id},
            )
            response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - 删除不可被网关故障卡住
        log.warning("failed to cancel local Codex task=%s: %s", task.id, exc)


async def delete_attribution_task(session: Session, run_id: int, task_id: int) -> None:
    task = get_attribution_task_or_404(session, run_id, task_id)
    await asyncio.gather(
        cancel_attribution_task(task.id),
        _cancel_codex_gateway_task(session, task),
    )
    session.execute(delete(AttributionTaskItem).where(AttributionTaskItem.task_id == task.id))
    session.delete(task)
    session.flush()


def mark_attribution_task_start_failed(task_id: int, exc: Exception) -> None:
    """任务已落库但后台协程启动失败时解除占用，允许用户重新发起。"""
    with session_scope() as session:
        task = session.get(AttributionTask, task_id)
        if task is None:
            return
        for item in session.scalars(
            select(AttributionTaskItem).where(
                AttributionTaskItem.task_id == task.id,
                AttributionTaskItem.status.in_(("pending", "running")),
            )
        ):
            item.status = "failed"
            item.error_msg = "归因任务启动失败，请重新发起"
            item.finished_at = datetime.utcnow()
        _refresh_task_counts(session, task)
        task.status = "failed"
        task.error_msg = f"归因任务启动失败：{type(exc).__name__}: {exc}"[:1000]
        task.finished_at = datetime.utcnow()


def reconcile_orphaned_attribution_tasks() -> int:
    """进程重启后明确标记中断任务，避免页面无限显示“分析中”。"""
    with session_scope() as session:
        tasks = list(session.scalars(
            select(AttributionTask).where(AttributionTask.status.in_(("queued", "running")))
        ))
        for task in tasks:
            for item in session.scalars(
                select(AttributionTaskItem).where(
                    AttributionTaskItem.task_id == task.id,
                    AttributionTaskItem.status.in_(("pending", "running")),
                )
            ):
                item.status = "failed"
                item.error_msg = "服务重启导致归因中断"
                item.finished_at = datetime.utcnow()
            _refresh_task_counts(session, task)
            task.status = "failed"
            task.error_msg = "服务重启导致归因任务中断，请重新发起"
            task.finished_at = datetime.utcnow()
        return len(tasks)


async def stop_attribution_tasks() -> None:
    active = [task for task in _task_futures.values() if not task.done()]
    for task in active:
        task.cancel()
    for task in active:
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
