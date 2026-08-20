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
from ..durable_queue import cancel_attribution_job, enqueue_attribution_job
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
from .attribution_taxonomy import current_optimization_category
from .judge_models import (
    ensure_attribution_model_reachable,
    get_judge_model_or_404,
    has_judge_model_api_key,
)


log = logging.getLogger(__name__)
_MAX_CONCURRENCY = 3
_task_futures: dict[int, asyncio.Task] = {}
_model_semaphores: dict[int, asyncio.Semaphore] = {}


def _semaphore(judge_model_id: int) -> asyncio.Semaphore:
    """同一归因模型共享并发上限，不同模型之间互不阻塞。"""

    model_id = int(judge_model_id)
    semaphore = _model_semaphores.get(model_id)
    if semaphore is None:
        semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
        _model_semaphores[model_id] = semaphore
    return semaphore


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
        "is_streaming": bool(task.is_streaming),
        "intake_open": bool(task.intake_open),
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
            "attempt_count": item.attempt_count,
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


def get_run_attribution_category_stats(session: Session, run_id: int) -> dict[str, Any]:
    """按 Case 的最新成功归因汇总一级、二级 cx-agent 问题分类。

    同一 Case 可能在多次归因任务中出现，也可能有多个扣分项落入同一分类。
    这里先选择该 Case 最新的成功快照，再用集合按分类去重，避免重试和重复扣分
    放大图表数量。
    """
    rows = session.execute(
        select(AttributionTaskItem, AttributionTask)
        .join(AttributionTask, AttributionTask.id == AttributionTaskItem.task_id)
        .where(
            AttributionTask.run_id == run_id,
            AttributionTaskItem.status == "success",
            AttributionTaskItem.analysis_json.is_not(None),
        )
        .order_by(
            AttributionTask.created_at.desc(),
            AttributionTask.id.desc(),
            AttributionTaskItem.id.desc(),
        )
    ).all()
    latest_by_case: dict[str, AttributionTaskItem] = {}
    for item, _task in rows:
        snapshot = item.analysis_json if isinstance(item.analysis_json, dict) else {}
        if (
            item.sample_id not in latest_by_case
            and snapshot.get("available") is True
            and isinstance(snapshot.get("analysis"), dict)
        ):
            latest_by_case[item.sample_id] = item

    summary = build_task_diagnostic_summary(
        (sample_id, item.analysis_json)
        for sample_id, item in latest_by_case.items()
    )
    first_cases: dict[str, set[str]] = {}
    second_cases: dict[tuple[str, str], set[str]] = {}
    first_labels: dict[str, str] = {}
    for cluster in summary.get("clusters") or []:
        if cluster.get("category") != "cx_agent_issue":
            continue
        classification = cluster.get("optimization_classification") or {}
        primary_key, primary_label, secondary_label = current_optimization_category(
            classification
        )
        sample_ids = {str(value) for value in cluster.get("sample_ids") or [] if value}
        if not sample_ids:
            continue
        first_labels[primary_key] = primary_label
        first_cases.setdefault(primary_key, set()).update(sample_ids)
        second_cases.setdefault((primary_key, secondary_label), set()).update(sample_ids)

    first_level = [
        {"key": key, "label": first_labels[key], "case_count": len(sample_ids)}
        for key, sample_ids in first_cases.items()
    ]
    second_level = [
        {
            "key": f"{primary_key}:{secondary_label}",
            "label": secondary_label,
            "case_count": len(sample_ids),
            "parent_key": primary_key,
            "parent_label": first_labels[primary_key],
        }
        for (primary_key, secondary_label), sample_ids in second_cases.items()
    ]
    order = {key: index for index, key in enumerate((
        "rag", "engineering", "reasoning", "prompt", "knowledge", "safety"
    ))}
    first_level.sort(key=lambda row: (-row["case_count"], order.get(row["key"], 99)))
    second_level.sort(key=lambda row: (
        -row["case_count"], order.get(str(row["parent_key"]), 99), str(row["label"])
    ))
    return {
        "attributed_case_count": len(latest_by_case),
        "first_level": first_level,
        "second_level": second_level,
    }


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
    include_passed: bool = False,
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
    ensure_attribution_model_reachable(model)
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
    target_ids = (
        ordered_ids
        if include_passed
        else [sample_id for sample_id in ordered_ids if not by_sample[sample_id].release_passed]
    )
    if not target_ids:
        raise HTTPException(
            status_code=422,
            detail="当前筛选结果没有可归因用例" if include_passed else "当前筛选结果没有不合格用例可归因",
        )
    task = AttributionTask(
        run_id=run.id,
        judge_model_id=model.id,
        judge_model_name=model.name,
        status="queued",
        requested_count=len(ordered_ids),
        total_count=len(target_ids),
        skipped_count=len(ordered_ids) - len(target_ids),
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
    session.add_all(AttributionTaskItem(task_id=task.id, sample_id=sample_id) for sample_id in target_ids)
    session.flush()
    return task


def create_streaming_attribution_task(
    session: Session,
    run: EvalRun,
    *,
    judge_model_id: int,
    created_by: str | None,
) -> AttributionTask:
    """为定时评测预建一个持续接收不合格 Case 的归因任务。"""
    active = session.scalar(
        select(AttributionTask.id).where(
            AttributionTask.run_id == run.id,
            AttributionTask.status.in_(("queued", "running")),
        )
    )
    if active is not None:
        raise HTTPException(status_code=409, detail="该评测已有进行中的归因任务")
    model = get_judge_model_or_404(session, judge_model_id)
    if not has_judge_model_api_key(model):
        raise HTTPException(status_code=422, detail=f"归因模型「{model.name}」未配置可用的 API Key")
    task = AttributionTask(
        run_id=run.id,
        judge_model_id=model.id,
        judge_model_name=model.name,
        status="queued",
        requested_count=0,
        total_count=0,
        skipped_count=0,
        is_streaming=True,
        intake_open=True,
        created_by=created_by,
    )
    session.add(task)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="该评测已有进行中的归因任务") from exc
    return task


def append_streaming_attribution_item(
    session: Session,
    task: AttributionTask,
    *,
    sample_id: str,
) -> bool:
    """幂等追加一个已完成的不合格 Case；返回是否真的新增。"""
    if not task.is_streaming or not task.intake_open:
        return False
    exists = session.scalar(
        select(AttributionTaskItem.id).where(
            AttributionTaskItem.task_id == task.id,
            AttributionTaskItem.sample_id == sample_id,
        )
    )
    if exists is not None:
        return False
    session.add(AttributionTaskItem(task_id=task.id, sample_id=sample_id))
    task.requested_count = int(task.requested_count or 0) + 1
    task.total_count = int(task.total_count or 0) + 1
    session.flush()
    return True


def close_streaming_attribution_task(
    session: Session, task: AttributionTask
) -> AttributionTask:
    """关闭持续接收口，并在已无待处理项时立即收敛任务终态。"""
    task.intake_open = False
    _refresh_task_counts(session, task)
    return task


def restore_streaming_attribution_snapshots(
    session: Session, task: AttributionTask
) -> int:
    """整批结果最终落库后，恢复已提前完成的 Case 归因快照。"""
    restored = 0
    rows = session.execute(
        select(AttributionTaskItem, CaseResultRow)
        .join(
            CaseResultRow,
            (CaseResultRow.run_id == task.run_id)
            & (CaseResultRow.sample_id == AttributionTaskItem.sample_id),
        )
        .where(
            AttributionTaskItem.task_id == task.id,
            AttributionTaskItem.status == "success",
            AttributionTaskItem.analysis_json.is_not(None),
        )
    ).all()
    for item, case_row in rows:
        snapshot = item.analysis_json if isinstance(item.analysis_json, dict) else {}
        if not snapshot.get("available") or not isinstance(snapshot.get("analysis"), dict):
            continue
        detail = dict(case_row.detail_json or {})
        detail["attribution_analysis"] = {
            "analysis": snapshot["analysis"],
            "metadata": dict(snapshot.get("metadata") or {}),
        }
        case_row.detail_json = detail
        restored += 1
    return restored


def _set_attribution_task_model(
    session: Session, task: AttributionTask, judge_model_id: int
) -> None:
    """将未完成/重试用例切换到用户本次选择的归因模型。"""
    model = get_judge_model_or_404(session, judge_model_id)
    if not has_judge_model_api_key(model):
        raise HTTPException(status_code=422, detail=f"归因模型「{model.name}」未配置可用的 API Key")
    ensure_attribution_model_reachable(model)
    task.judge_model_id = model.id
    task.judge_model_name = model.name


def resume_attribution_task(
    session: Session, run_id: int, task_id: int, judge_model_id: int
) -> AttributionTask:
    """在原任务中继续归因，只重新排队未成功完成的 Case。

    服务重启或模型调用异常后，已成功写入 ``analysis_json`` 的条目不可被覆盖；
    仅把 pending/running/failed 条目恢复为 pending，并按本次选择的模型继续处理。
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

    _set_attribution_task_model(session, task, judge_model_id)

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


def rerun_attribution_task_items(
    session: Session,
    run_id: int,
    task_id: int,
    sample_ids: list[str],
    judge_model_id: int,
) -> AttributionTask:
    """在原归因任务内重新分析指定 Case，不创建新的任务记录。"""
    task = get_attribution_task_or_404(session, run_id, task_id)
    if task.status in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="该归因任务正在执行，请等待完成后重试")
    other_active = session.scalar(
        select(AttributionTask.id).where(
            AttributionTask.run_id == run_id,
            AttributionTask.id != task.id,
            AttributionTask.status.in_(("queued", "running")),
        )
    )
    if other_active is not None:
        raise HTTPException(status_code=409, detail="该评测已有其他进行中的归因任务")

    ordered_ids = list(dict.fromkeys(value.strip() for value in sample_ids if value.strip()))
    if not ordered_ids:
        raise HTTPException(status_code=422, detail="请至少选择一个用例")
    items = list(session.scalars(
        select(AttributionTaskItem).where(
            AttributionTaskItem.task_id == task.id,
            AttributionTaskItem.sample_id.in_(ordered_ids),
        )
    ))
    by_sample = {item.sample_id: item for item in items}
    unknown = [sample_id for sample_id in ordered_ids if sample_id not in by_sample]
    if unknown:
        raise HTTPException(status_code=422, detail=f"归因任务中不存在用例 {unknown[0]}")

    _set_attribution_task_model(session, task, judge_model_id)

    for sample_id in ordered_ids:
        item = by_sample[sample_id]
        item.status = "pending"
        item.attempt_count = int(item.attempt_count or 0) + 1
        item.error_msg = ""
        item.analysis_json = None
        item.started_at = None
        item.finished_at = None

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
    # 流水线仍在接收评测结果时，即使当前批次已经消费完也不能提前结束任务。
    if task.is_streaming and task.intake_open:
        return
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


def _mark_task_model_unavailable(task_id: int, detail: str) -> None:
    """把网关离线视为任务级故障，不逐条消耗待归因 Case。"""
    with session_scope() as session:
        task = session.get(AttributionTask, task_id)
        if task is None:
            return
        task.status = "failed"
        task.error_msg = detail[:2000]
        task.finished_at = datetime.utcnow()


async def _run_item(task_id: int, item_id: int) -> None:
    try:
        # 先读取模型键再等待并发槽位。同一模型的多个任务共享 3 个槽位；
        # 不同模型各自执行，避免先启动的慢模型饿死后续模型任务。
        with session_scope() as session:
            task = session.get(AttributionTask, task_id)
            if task is None:
                return
            judge_model_id = task.judge_model_id
        async with _semaphore(judge_model_id):
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


async def run_attribution_task(task_id: int, *, recover_interrupted_items: bool = False) -> None:
    """执行一个归因任务。

    生产环境由持久化 Worker 调用。若上一个 Worker 在模型调用期间重启，
    ``running`` 条目没有机会写入终态；新 Worker 领取到同一个租约任务时把
    它们恢复为 ``pending``，从该 Case 继续，不覆盖已成功的归因快照。
    """
    from medeval.judges.llm_backend import configure_llm_rate_limit, reset_llm_rate_limit

    # 归因本身按 3 条并行；建立任务级稳定限流上下文，既不会继承同一 Worker
    # 上一个重判任务的 semaphore，也不会被同时运行的评测任务替换。
    configure_llm_rate_limit(_MAX_CONCURRENCY, 0.0)
    try:
        model_preflight_error: str | None = None
        with session_scope() as session:
            task = session.get(AttributionTask, task_id)
            if task is None:
                return
            model = session.get(JudgeModelConfig, task.judge_model_id)
            if model is None:
                model_preflight_error = "归因模型已被删除，请重新选择模型后继续归因"
            else:
                try:
                    ensure_attribution_model_reachable(model)
                except HTTPException as exc:
                    model_preflight_error = str(exc.detail)

        if model_preflight_error:
            # 创建任务到 Worker 领取之间网关可能下线。此时不把所有 pending
            # Case 依次请求一次再标失败，恢复网关后可直接“继续归因”。
            _mark_task_model_unavailable(task_id, model_preflight_error)
            log.warning("attribution task=%s model preflight failed: %s", task_id, model_preflight_error)
            return

        _set_task_running(task_id)
        recovered = False
        while True:
            with session_scope() as session:
                task = session.get(AttributionTask, task_id)
                if task is None:
                    return
                if recover_interrupted_items and not recovered:
                    for item in session.scalars(
                        select(AttributionTaskItem).where(
                            AttributionTaskItem.task_id == task_id,
                            AttributionTaskItem.status == "running",
                        )
                    ):
                        item.status = "pending"
                        item.error_msg = ""
                        item.started_at = None
                    recovered = True
                item_ids = list(session.scalars(
                    select(AttributionTaskItem.id)
                    .where(
                        AttributionTaskItem.task_id == task_id,
                        AttributionTaskItem.status == "pending",
                    )
                    .order_by(AttributionTaskItem.id)
                ))
                intake_open = bool(task.is_streaming and task.intake_open)
                if not item_ids and not intake_open:
                    _refresh_task_counts(session, task)
                    return
            if item_ids:
                await asyncio.gather(*(_run_item(task_id, item_id) for item_id in item_ids))
                continue
            # 评测尚未完成：保持同一个 Worker Job，等待下一个不合格 Case 追加。
            await asyncio.sleep(0.5)
    finally:
        reset_llm_rate_limit()
        _task_futures.pop(task_id, None)


def start_attribution_task(task_id: int) -> None:
    """提交归因任务。

    database 模式下只入队，由独立 Worker 领取；因此 app 重启、前端刷新和
    发布均不会丢失归因协程。in_process 保留给本地开发/测试兼容。
    """
    from ..settings import get_settings

    with session_scope() as session:
        task = session.get(AttributionTask, task_id)
        if task is None:
            return
        run_id = task.run_id
    if get_settings().job_runner_mode == "database":
        enqueue_attribution_job(run_id, task_id)
        return
    active = _task_futures.get(task_id)
    if active is not None and not active.done():
        return
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
    # database Worker 中的归因任务不在 Web 进程内，必须显式取消其租约 Job；
    # 否则删除后 Worker 仍可能继续发送模型请求。
    cancel_attribution_job(task.id)
    session.execute(delete(AttributionTaskItem).where(AttributionTaskItem.task_id == task.id))
    session.delete(task)
    session.flush()


async def delete_attribution_tasks_for_run(session: Session, run_id: int) -> int:
    """终止并删除评测下的全部归因任务及逐 Case 明细。"""
    task_ids = list(session.scalars(
        select(AttributionTask.id)
        .where(AttributionTask.run_id == run_id)
        .order_by(AttributionTask.id)
    ))
    for task_id in task_ids:
        await delete_attribution_task(session, run_id, task_id)
    return len(task_ids)


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


def mark_attribution_task_worker_failed(task_id: int, error: str) -> None:
    """Worker 无法执行归因 Job 时收敛任务，保留已完成结果以便原地继续。"""
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
            item.error_msg = "归因 Worker 异常中断，可继续归因"
            item.finished_at = datetime.utcnow()
        _refresh_task_counts(session, task)
        # _refresh_task_counts 会根据已成功/失败 Case 生成 partial/failed 终态；
        # error_msg 用于页面说明为何需要用户继续，而不是显示为一直运行。
        task.error_msg = f"归因 Worker 异常：{error}"[:1000]
        task.finished_at = datetime.utcnow()


def reconcile_orphaned_attribution_tasks() -> int:
    """启动时补齐遗失的归因队列任务，并恢复被中断的 Case。

    评测任务已由数据库租约队列保证重启恢复；归因同样走该机制。历史版本
    创建的进程内归因没有对应 EvaluationJob 时，在此补入队列。已有活跃
    Worker Job 时不改动，避免 Web 服务发布影响正在生成的归因。
    """
    from ..settings import get_settings

    if get_settings().job_runner_mode != "database":
        # 本地兼容模式没有独立 Worker，仍明确把被中断任务收敛为可见失败，
        # 让用户可以点击“继续归因”。
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

    recover: list[tuple[int, int]] = []
    with session_scope() as session:
        tasks = list(session.scalars(
            select(AttributionTask).where(AttributionTask.status.in_(("queued", "running")))
        ))
        for task in tasks:
            # enqueue_attribution_job 内部会再次去重，这里不强依赖 JSON 方言；
            # 先记录，等当前事务提交后再创建持久化 Job。
            recover.append((task.run_id, task.id))
    for run_id, task_id in recover:
        enqueue_attribution_job(run_id, task_id)
    return len(recover)


async def stop_attribution_tasks() -> None:
    active = [task for task in _task_futures.values() if not task.done()]
    for task in active:
        task.cancel()
    for task in active:
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
