"""永久临时评测的幂等、每日 Run 汇总、租约队列与进程内兼容调度。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import hashlib
import json
import logging
import os
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from medeval.models import CaseResult, ChatMessage, ConversationTrace, TestCase

from ..db import session_scope
from ..ingest import upsert_case_result
from ..models_db import Benchmark, CaseResultRow, EvalRun, TemporaryEvaluation
from ..schemas import (
    OpenTemporaryCaseSource,
    OpenTemporaryEvaluationCreate,
    OpenTemporaryEvaluationCreatedOut,
    OpenTemporaryEvaluationError,
    OpenTemporaryEvaluationOut,
    OpenTemporaryEvaluationStatusOut,
)
from ..settings import get_settings
from . import temporary_evaluation as evaluator


log = logging.getLogger(__name__)

ACTIVE_STATUSES = ("pending", "running")
TERMINAL_STATUSES = ("success", "failed")
DEFAULT_RETRY_AFTER_SECONDS = 5
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_in_process_tasks: dict[str, asyncio.Task] = {}
_in_process_semaphore: asyncio.Semaphore | None = None


def _now() -> datetime:
    return datetime.utcnow()


def _group_date(now: datetime | None = None) -> str:
    """用上海自然日聚合 Open API 临时评测。"""
    utc_now = now or _now()
    return utc_now.replace(tzinfo=ZoneInfo("UTC")).astimezone(SHANGHAI_TZ).date().isoformat()


def _request_digest(payload: OpenTemporaryEvaluationCreate) -> str:
    canonical = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _contract_fingerprint(case: TestCase) -> str:
    return hashlib.sha256(
        evaluator._evaluation_contract_key(case).encode("utf-8")
    ).hexdigest()


def _status_url(evaluation_id: str) -> str:
    return f"/api/open/v1/temporary-evaluations/{evaluation_id}"


def _created_out(row: TemporaryEvaluation) -> OpenTemporaryEvaluationCreatedOut:
    return OpenTemporaryEvaluationCreatedOut(
        evaluation_id=row.evaluation_id,
        external_request_id=row.external_request_id,
        status=row.status,
        status_url=_status_url(row.evaluation_id),
        expires_at=row.expires_at,
    )


def _status_out(row: TemporaryEvaluation) -> OpenTemporaryEvaluationStatusOut:
    result = (
        OpenTemporaryEvaluationOut.model_validate(row.result_payload)
        if row.status == "success" and row.result_payload
        else None
    )
    error = (
        OpenTemporaryEvaluationError(
            code=row.error_code or "temporary_evaluation_failed",
            message=row.error_message or "临时评测失败，请稍后重试",
            retryable=bool(row.retryable),
        )
        if row.status == "failed"
        else None
    )
    return OpenTemporaryEvaluationStatusOut(
        **_created_out(row).model_dump(),
        result=result,
        error=error,
        retry_after_seconds=(
            DEFAULT_RETRY_AFTER_SECONDS if row.status in ACTIVE_STATUSES else None
        ),
    )


def cleanup_expired_temporary_evaluations() -> int:
    """兼容旧调用方：临时评测已改为永久保存，不再执行物理清理。"""
    return 0


def _daily_run(session: Session, *, api_key_id: int, now: datetime) -> EvalRun:
    """取当天临时评测聚合 Run；同一上海自然日只有一条。"""
    group_date = _group_date(now)
    existing = session.scalar(
        select(EvalRun).where(EvalRun.temporary_group_date == group_date)
    )
    if existing is not None:
        return existing

    row = EvalRun(
        run_slug=f"open-api-temporary-{group_date}",
        name=f"{group_date} 临时评测",
        description="通过 Open API 创建的临时单轮评测，按上海自然日汇总。",
        status="running",
        trigger_type="open_api",
        open_api_key_id=api_key_id,
        temporary_group_date=group_date,
        created_by="OpenAPI",
        progress={"phase": "temporary_evaluation", "label": "临时评测", "done": 0, "total": 0},
        config_snapshot={"temporary_evaluations": True, "group_date": group_date},
    )
    # 多个 Open API 请求可能在同一时刻到达。唯一键负责收口，保存点让冲突后
    # 可以直接读取已由另一个请求创建的当天 Run，而不回滚本次临时请求。
    try:
        with session.begin_nested():
            session.add(row)
            session.flush()
        return row
    except IntegrityError:
        existing = session.scalar(
            select(EvalRun).where(EvalRun.temporary_group_date == group_date)
        )
        if existing is None:
            raise
        return existing


def _refresh_daily_run(session: Session, run_id: int | None) -> None:
    """临时请求完成一条即同步常规 Run 汇总，供列表、看板和用例详情复用。"""
    if run_id is None:
        return
    run = session.get(EvalRun, run_id)
    if run is None:
        return
    rows = list(
        session.scalars(
            select(TemporaryEvaluation)
            .where(TemporaryEvaluation.run_id == run_id)
            .order_by(TemporaryEvaluation.id)
        )
    )
    result_rows = list(
        session.scalars(select(CaseResultRow).where(CaseResultRow.run_id == run_id))
    )
    total = len(rows)
    done = sum(item.status in TERMINAL_STATUSES for item in rows)
    judged_rows = [item for item in result_rows if not item.judge_error]
    passed = sum(bool(item.release_passed) for item in judged_rows)
    medical_safety_failed = sum(
        not bool(item.medical_safety_passed) for item in judged_rows
    )
    scores = [
        float(item.composite_score)
        for item in judged_rows
        if item.composite_score is not None
    ]
    run.total = total
    run.passed = passed
    run.pass_rate = (passed / total) if total else 0.0
    run.medical_safety_failed = medical_safety_failed
    run.n_runs = 1
    run.progress = {
        "phase": "temporary_evaluation",
        "label": "临时评测",
        "done": done,
        "total": total,
    }
    run.grading = {"avg_composite": sum(scores) / len(scores) if scores else None}
    if rows:
        run.started_at = min(
            (item.started_at or item.created_at or _now()) for item in rows
        )
    if total and done == total:
        run.status = "success"
        run.error_msg = ""
        run.finished_at = max(
            (item.finished_at or item.updated_at or _now()) for item in rows
        )
    else:
        run.status = "running"
        run.finished_at = None


def create_temporary_evaluation(
    session: Session,
    payload: OpenTemporaryEvaluationCreate,
    *,
    api_key_id: int,
) -> tuple[OpenTemporaryEvaluationCreatedOut, bool]:
    """冻结评分契约并创建任务；返回值第二项表示是否新建。"""
    now = _now()
    digest = _request_digest(payload)
    if payload.external_request_id:
        existing = session.scalar(
            select(TemporaryEvaluation).where(
                TemporaryEvaluation.api_key_id == api_key_id,
                TemporaryEvaluation.external_request_id == payload.external_request_id,
            )
        )
        if existing is not None:
            if existing.request_digest != digest:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "同一 external_request_id 已用于不同的临时评测请求，"
                        "请复用原请求或更换流水号"
                    ),
                )
            return _created_out(existing), False

    evaluation_id = f"temporary_{uuid4().hex}"
    # 创建阶段完成所有确定性校验，并冻结本次实际采用的 Case 评分契约。
    _override, judge_model_id, judge_model_name = evaluator._judge_override(
        session, payload.judge_model_id
    )
    case, case_source = evaluator._temporary_case(session, payload, evaluation_id)
    benchmark_version = ""
    if case_source is not None:
        benchmark = session.get(Benchmark, case_source.benchmark_id)
        benchmark_version = benchmark.version if benchmark is not None else ""

    run = _daily_run(session, api_key_id=api_key_id, now=now)
    row = TemporaryEvaluation(
        evaluation_id=evaluation_id,
        api_key_id=api_key_id,
        external_request_id=payload.external_request_id,
        request_digest=digest,
        request_payload=payload.model_dump(mode="json"),
        case_snapshot=case.model_dump(mode="json"),
        case_source=case_source.model_dump(mode="json") if case_source else {},
        benchmark_id=case_source.benchmark_id if case_source else None,
        benchmark_version=benchmark_version,
        sample_id=case_source.sample_id if case_source else "",
        contract_fingerprint=_contract_fingerprint(case),
        judge_model_id=judge_model_id,
        judge_model_name=judge_model_name or "",
        run_id=run.id,
        status="pending",
        expires_at=None,
    )
    session.add(row)
    try:
        session.flush()
        _refresh_daily_run(session, run.id)
        # 后台任务必须在提交前看到完整请求、评分契约和归属 Run，因此这里显式提交。
        session.commit()
    except IntegrityError:
        session.rollback()
        if not payload.external_request_id:
            raise
        existing = session.scalar(
            select(TemporaryEvaluation).where(
                TemporaryEvaluation.api_key_id == api_key_id,
                TemporaryEvaluation.external_request_id == payload.external_request_id,
            )
        )
        if existing is None or existing.request_digest != digest:
            raise HTTPException(
                status_code=409,
                detail="同一 external_request_id 已被其他请求占用",
            )
        return _created_out(existing), False
    return _created_out(row), True


def get_temporary_evaluation(
    session: Session,
    evaluation_id: str,
    *,
    api_key_id: int,
) -> OpenTemporaryEvaluationStatusOut:
    row = session.scalar(
        select(TemporaryEvaluation).where(
            TemporaryEvaluation.evaluation_id == evaluation_id,
            TemporaryEvaluation.api_key_id == api_key_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="临时评测不存在或无权访问")
    return _status_out(row)


def claim_temporary_evaluation(
    owner: str,
    lease_seconds: int,
    *,
    evaluation_id: str | None = None,
) -> TemporaryEvaluation | None:
    """领取最早 pending 任务，或接管租约过期的 running 任务。"""
    now = _now()
    with session_scope() as session:
        stmt = (
            select(TemporaryEvaluation)
            .where(
                or_(
                    TemporaryEvaluation.status == "pending",
                    (
                        (TemporaryEvaluation.status == "running")
                        & (TemporaryEvaluation.lease_expires_at.is_not(None))
                        & (TemporaryEvaluation.lease_expires_at < now)
                    ),
                ),
            )
            .order_by(TemporaryEvaluation.id)
            .limit(1)
        )
        if evaluation_id is not None:
            stmt = stmt.where(TemporaryEvaluation.evaluation_id == evaluation_id)
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        row = session.scalar(stmt)
        if row is None:
            return None
        row.status = "running"
        row.lease_owner = owner
        row.lease_expires_at = now + timedelta(seconds=max(10, lease_seconds))
        row.heartbeat_at = now
        row.attempts = int(row.attempts or 0) + 1
        row.started_at = row.started_at or now
        row.error_code = ""
        row.error_message = ""
        row.retryable = False
        session.flush()
        session.expunge(row)
        return row


def heartbeat_temporary_evaluation(
    evaluation_id: str,
    owner: str,
    lease_seconds: int,
) -> bool:
    with session_scope() as session:
        row = session.scalar(
            select(TemporaryEvaluation).where(
                TemporaryEvaluation.evaluation_id == evaluation_id
            )
        )
        if row is None or row.status != "running" or row.lease_owner != owner:
            return False
        row.heartbeat_at = _now()
        row.lease_expires_at = row.heartbeat_at + timedelta(
            seconds=max(10, lease_seconds)
        )
        return True


def requeue_temporary_evaluation(evaluation_id: str, owner: str) -> bool:
    with session_scope() as session:
        row = session.scalar(
            select(TemporaryEvaluation).where(
                TemporaryEvaluation.evaluation_id == evaluation_id
            )
        )
        if row is None or row.status != "running" or row.lease_owner != owner:
            return False
        row.status = "pending"
        row.lease_owner = None
        row.lease_expires_at = None
        row.heartbeat_at = _now()
        return True


def _finish_success(
    evaluation_id: str,
    owner: str,
    result: OpenTemporaryEvaluationOut,
    case_result: CaseResult,
) -> bool:
    with session_scope() as session:
        row = session.scalar(
            select(TemporaryEvaluation).where(
                TemporaryEvaluation.evaluation_id == evaluation_id
            )
        )
        if row is None or row.status != "running" or row.lease_owner != owner:
            return False
        row.status = "success"
        row.result_payload = result.model_dump(mode="json")
        row.judge_model_id = result.judge_model_id
        row.judge_model_name = result.judge_model_name
        row.finished_at = _now()
        row.lease_owner = None
        row.lease_expires_at = None
        row.heartbeat_at = row.finished_at
        if row.run_id is not None:
            upsert_case_result(session, row.run_id, case_result)
        _refresh_daily_run(session, row.run_id)
        return True


def _failure_from_exception(exc: BaseException) -> tuple[str, str, bool]:
    if isinstance(exc, HTTPException):
        code = {
            404: "judge_model_not_found",
            409: "benchmark_contract_conflict",
            422: "temporary_evaluation_invalid",
            502: "judge_evaluation_failed",
            503: "benchmark_index_unavailable",
        }.get(exc.status_code, "temporary_evaluation_failed")
        return code, str(exc.detail), exc.status_code in {429, 502, 503, 504}
    if isinstance(exc, ValidationError):
        return (
            "temporary_evaluation_snapshot_invalid",
            "临时评测数据校验失败，请重新创建任务",
            False,
        )
    return (
        "temporary_evaluation_internal_error",
        "临时评测执行失败，请稍后重试",
        True,
    )


def _failed_case_result(row: TemporaryEvaluation, message: str) -> CaseResult:
    """把判分异常也写入标准用例明细，避免临时 Run 出现“有任务无明细”。"""
    payload = OpenTemporaryEvaluationCreate.model_validate(row.request_payload)
    case = TestCase.model_validate(row.case_snapshot)
    return CaseResult(
        case=case,
        trace=ConversationTrace(
            messages=[
                ChatMessage(role="user", content=payload.question),
                ChatMessage(role="assistant", content=payload.answer),
            ],
            error=message,
        ),
        verdicts=[],
        medical_safety_passed=True,
        release_passed=False,
        judge_error=True,
        failure_tags=["判分异常"],
        grade="判分异常",
        stability="stable_fail",
    )


def _finish_failure(evaluation_id: str, owner: str, exc: BaseException) -> bool:
    code, message, retryable = _failure_from_exception(exc)
    with session_scope() as session:
        row = session.scalar(
            select(TemporaryEvaluation).where(
                TemporaryEvaluation.evaluation_id == evaluation_id
            )
        )
        if row is None or row.status != "running" or row.lease_owner != owner:
            return False
        row.status = "failed"
        row.result_payload = None
        row.error_code = code
        row.error_message = message[:4000]
        row.retryable = retryable
        row.finished_at = _now()
        row.lease_owner = None
        row.lease_expires_at = None
        row.heartbeat_at = row.finished_at
        if row.run_id is not None:
            upsert_case_result(
                session,
                row.run_id,
                _failed_case_result(row, row.error_message),
            )
        _refresh_daily_run(session, row.run_id)
        return True


async def _evaluate_snapshot(
    evaluation_id: str,
) -> tuple[OpenTemporaryEvaluationOut, CaseResult]:
    """从临时表重建已冻结的请求与评分契约并执行 Judge。"""
    with session_scope() as session:
        row = session.scalar(
            select(TemporaryEvaluation).where(
                TemporaryEvaluation.evaluation_id == evaluation_id
            )
        )
        if row is None:
            raise HTTPException(status_code=404, detail="临时评测不存在")
        payload = OpenTemporaryEvaluationCreate.model_validate(row.request_payload)
        case = TestCase.model_validate(row.case_snapshot)
        case_source = (
            OpenTemporaryCaseSource.model_validate(row.case_source)
            if row.case_source
            else None
        )
        return await evaluator.evaluate_temporary_conversation_with_result(
            session,
            payload,
            evaluation_id=evaluation_id,
            case_snapshot=case,
            case_source_snapshot=case_source,
        )


async def execute_claimed_temporary_evaluation(
    row: TemporaryEvaluation,
    owner: str,
) -> None:
    """执行已领取任务，并用租约阻止迟到 Worker 覆盖新结果。"""
    settings = get_settings()
    task = asyncio.create_task(
        _evaluate_snapshot(row.evaluation_id),
        name=f"temporary-evaluation-{row.evaluation_id}",
    )
    try:
        while not task.done():
            try:
                await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=max(1, settings.job_heartbeat_seconds),
                )
            except asyncio.TimeoutError:
                if not heartbeat_temporary_evaluation(
                    row.evaluation_id,
                    owner,
                    settings.job_lease_seconds,
                ):
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    return
        result, case_result = await task
    except asyncio.CancelledError:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        requeue_temporary_evaluation(row.evaluation_id, owner)
        raise
    except Exception as exc:  # noqa: BLE001 - 失败必须结构化落入临时任务
        if not isinstance(exc, HTTPException):
            log.exception("临时评测执行失败 evaluation_id=%s", row.evaluation_id)
        _finish_failure(row.evaluation_id, owner, exc)
    else:
        _finish_success(row.evaluation_id, owner, result, case_result)


def _semaphore() -> asyncio.Semaphore:
    global _in_process_semaphore
    if _in_process_semaphore is None:
        _in_process_semaphore = asyncio.Semaphore(
            max(1, get_settings().max_concurrent_jobs)
        )
    return _in_process_semaphore


async def _run_in_process(evaluation_id: str) -> None:
    owner = f"in-process-{os.getpid()}-{evaluation_id}"
    async with _semaphore():
        row = claim_temporary_evaluation(
            owner,
            get_settings().job_lease_seconds,
            evaluation_id=evaluation_id,
        )
        if row is not None:
            await execute_claimed_temporary_evaluation(row, owner)


def schedule_temporary_evaluation(evaluation_id: str) -> None:
    """开发/测试兼容模式直接调度；生产 database 模式由独立 Worker 领取。"""
    if get_settings().job_runner_mode == "database":
        return
    existing = _in_process_tasks.get(evaluation_id)
    if existing is not None and not existing.done():
        return
    task = asyncio.create_task(
        _run_in_process(evaluation_id),
        name=f"temporary-evaluation-submit-{evaluation_id}",
    )
    _in_process_tasks[evaluation_id] = task
    task.add_done_callback(lambda _task: _in_process_tasks.pop(evaluation_id, None))


def _reconcile_in_process_tasks() -> list[str]:
    """进程内模式重启后没有存活 Worker，安全地把 running 任务重新排队。"""
    with session_scope() as session:
        rows = list(
            session.scalars(
                select(TemporaryEvaluation).where(
                    TemporaryEvaluation.status.in_(ACTIVE_STATUSES),
                )
            )
        )
        for row in rows:
            row.status = "pending"
            row.lease_owner = None
            row.lease_expires_at = None
        return [row.evaluation_id for row in rows]


def start_temporary_evaluation_service() -> None:
    if get_settings().job_runner_mode != "database":
        for evaluation_id in _reconcile_in_process_tasks():
            schedule_temporary_evaluation(evaluation_id)


async def stop_temporary_evaluation_service() -> None:
    global _in_process_semaphore
    tasks = [task for task in _in_process_tasks.values() if not task.done()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    _in_process_tasks.clear()
    _in_process_semaphore = None
