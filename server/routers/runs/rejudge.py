"""runs 离线重判、续跑与单用例试判。"""

from __future__ import annotations

from typing import Optional

from fastapi import Body, Depends, HTTPException
from sqlalchemy.orm import Session

from medeval import trace_store

from ...benchmarks import BenchmarkValidationError
from ...db import get_session
from ...jobs import get_job_runner
from ...models_db import EvalRun
from ...schemas import (
    PreviewRejudgeRequest,
    PreviewRejudgeResponse,
    RejudgeRequest,
    RunSummaryOut,
)
from ...services.case_query import case_row_or_404
from ...services.rejudge_launch import (
    RejudgeLaunchError,
    build_preview_response,
    prepare_rejudge_derived_run,
    resolve_preview_case_override,
    validate_preview_request,
)
from ...services.runs import create_derived_run, get_run_or_404, source_out_dir
from ._router import router


@router.post("/{run_id}/rejudge", response_model=RunSummaryOut, status_code=201)
async def rejudge_run(
    run_id: int,
    payload: Optional[RejudgeRequest] = Body(default=None),
    session: Session = Depends(get_session),
) -> EvalRun:
    payload = payload or RejudgeRequest()
    source = get_run_or_404(session, run_id)
    try:
        derived, judge_ov = prepare_rejudge_derived_run(session, source, payload)
    except RejudgeLaunchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    from . import build_rejudge_job

    job = build_rejudge_job(
        derived.id,
        source_run_id=source.id,
        run_name=derived.name,
        judge_override=judge_ov.model_dump(exclude_none=True) if judge_ov else None,
        cases_benchmark_id=payload.cases_benchmark_id,
        only_release_failed=payload.only_release_failed,
    )
    await get_job_runner().submit(derived.id, job)
    return session.get(EvalRun, derived.id)


@router.post("/{run_id}/resume", response_model=RunSummaryOut, status_code=201)
async def resume_run(
    run_id: int, session: Session = Depends(get_session)
) -> EvalRun:
    source = get_run_or_404(session, run_id)
    if source.status in ("running", "pending"):
        raise HTTPException(status_code=400, detail="运行中或等待中的评测不可续跑")
    out_dir = source_out_dir(source)
    if out_dir is None:
        raise HTTPException(status_code=400, detail="源 run 产物目录缺失，无法续跑")
    has_report = (out_dir / "report.json").is_file()
    has_traces = (out_dir / trace_store.TRACES_GZ).is_file() or (
        out_dir / trace_store.PARTIAL
    ).is_file()
    if not has_traces and not has_report:
        raise HTTPException(
            status_code=400,
            detail="源 run 无可复用留痕（从未落盘或已被存储治理清理），无法续跑",
        )
    if not has_report and source.benchmark_id is None:
        raise HTTPException(
            status_code=400, detail="源 run 未关联 benchmark，无法重建用例集续跑"
        )

    derived = create_derived_run(session, source, suffix="续跑")
    from . import build_resume_job

    job = build_resume_job(derived.id, source_run_id=source.id, run_name=derived.name)
    await get_job_runner().submit(derived.id, job)
    return session.get(EvalRun, derived.id)


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
