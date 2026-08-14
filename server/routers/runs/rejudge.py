"""runs 离线重判、续跑与单用例试判。"""

from __future__ import annotations

from typing import Optional

from fastapi import Body, Depends, HTTPException
from sqlalchemy.orm import Session

from ...benchmarks import BenchmarkValidationError
from ...auth import get_current_user_optional
from ...db import get_session
from ...jobs import get_job_runner
from ...models_db import EvalRun, FeishuUser
from ...schemas import (
    CaseRetryRequest,
    PreviewRejudgeRequest,
    PreviewRejudgeResponse,
    RejudgeRequest,
    RunSummaryOut,
)
from ...services.case_query import case_row_or_404
from ...services.case_retry import (
    CaseRetryError,
    cancel_cases_retry,
    launch_case_retry,
    launch_cases_retry,
)
from ...services.eval_resume import launch_resume_run
from ...services.rejudge_launch import (
    RejudgeLaunchError,
    build_preview_response,
    launch_rejudge_run,
    resolve_preview_case_override,
    validate_preview_request,
)
from ._router import router


@router.post("/{run_id}/rejudge", response_model=RunSummaryOut, status_code=201)
async def rejudge_run(
    run_id: int,
    payload: Optional[RejudgeRequest] = Body(default=None),
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> EvalRun:
    payload = payload or RejudgeRequest()
    try:
        from . import build_rejudge_job

        return await launch_rejudge_run(
            session,
            run_id,
            payload,
            created_by=current_user.name if current_user else None,
            job_runner=get_job_runner(),
            build_rejudge_job=build_rejudge_job,
        )
    except RejudgeLaunchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{run_id}/resume", response_model=RunSummaryOut, status_code=201)
async def resume_run(
    run_id: int,
    session: Session = Depends(get_session),
) -> EvalRun:
    from . import build_resume_job

    return await launch_resume_run(
        session,
        run_id,
        job_runner=get_job_runner(),
        build_resume_job=build_resume_job,
    )


@router.post("/{run_id}/cases/{sample_id}/retry", response_model=RunSummaryOut, status_code=202)
async def retry_case(
    run_id: int,
    sample_id: str,
    session: Session = Depends(get_session),
) -> EvalRun:
    """重新执行单个用例的 agent 调用和判分，并原位替换该 Case 结果。"""
    try:
        from . import build_retry_case_job

        return await launch_case_retry(
            session,
            run_id,
            sample_id,
            job_runner=get_job_runner(),
            build_retry_case_job=build_retry_case_job,
        )
    except CaseRetryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{run_id}/cases/retry", response_model=RunSummaryOut, status_code=202)
async def retry_cases(
    run_id: int,
    payload: CaseRetryRequest,
    session: Session = Depends(get_session),
) -> EvalRun:
    """重新执行所选 Case 的 Agent 调用和完整判分，原位覆盖历史结果。"""
    try:
        from . import build_retry_cases_job

        return await launch_cases_retry(
            session,
            run_id,
            sample_ids=payload.sample_ids,
            job_runner=get_job_runner(),
            build_retry_cases_job=build_retry_cases_job,
        )
    except CaseRetryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{run_id}/cases/retry/cancel", response_model=RunSummaryOut)
async def cancel_retry_cases(
    run_id: int,
    session: Session = Depends(get_session),
) -> EvalRun:
    """终止正在执行的所选用例重评，保留原评测记录。"""
    try:
        return await cancel_cases_retry(
            session,
            run_id,
            job_runner=get_job_runner(),
        )
    except CaseRetryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post(
    "/{run_id}/cases/{sample_id}/preview-rejudge",
    response_model=PreviewRejudgeResponse,
)
async def preview_rejudge_case_route(
    run_id: int,
    sample_id: str,
    payload: Optional[PreviewRejudgeRequest] = Body(default=None),
    session: Session = Depends(get_session),
) -> PreviewRejudgeResponse:
    payload = payload or PreviewRejudgeRequest()
    try:
        validate_preview_request(session, run_id, sample_id)
    except RejudgeLaunchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    row = case_row_or_404(session, run_id, sample_id)
    override = resolve_preview_case_override(payload, sample_id)
    from . import preview_rejudge_case

    try:
        new_result = await preview_rejudge_case(
            source_run_id=run_id, sample_id=sample_id, case_override=override
        )
    except BenchmarkValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return build_preview_response(row, sample_id, new_result)
