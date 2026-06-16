"""runs CRUD、进度与 diff。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from ...constants import LIST_LIMIT_DEFAULT, LIST_LIMIT_MAX
from ...db import get_session
from ...jobs import get_job_runner
from ...models_db import EvalRun
from ...schemas import ProgressOut, RunCreate, RunDetailOut, RunRenameRequest, RunSummaryOut
from ...services import runs as runs_svc
from ._router import router


@router.post("", response_model=RunSummaryOut, status_code=201)
async def create_run(
    payload: RunCreate, session: Session = Depends(get_session)
) -> EvalRun:
    plan = runs_svc.prepare_create_run(session, payload)
    from . import build_eval_job

    job = build_eval_job(
        plan.run.id,
        benchmark_id=plan.benchmark_id,
        run_name=plan.run_name,
        score_profiles=plan.score_profiles,
        levels=plan.levels,
        limit=plan.limit,
        repeat=plan.repeat,
        judge_full=plan.judge_full,
        adapter_full=plan.adapter_full,
    )
    await get_job_runner().submit(plan.run.id, job)
    return plan.run


@router.get("", response_model=list[RunSummaryOut])
def list_runs(
    benchmark_id: Optional[int] = None,
    limit: int = Query(
        LIST_LIMIT_DEFAULT, ge=1, le=LIST_LIMIT_MAX, description="分页大小"
    ),
    offset: int = Query(0, ge=0, description="分页偏移"),
    session: Session = Depends(get_session),
) -> list[EvalRun]:
    return runs_svc.list_runs(
        session, benchmark_id=benchmark_id, limit=limit, offset=offset
    )


@router.get("/{run_id}", response_model=RunDetailOut)
def get_run(run_id: int, session: Session = Depends(get_session)) -> EvalRun:
    return runs_svc.get_run_or_404(session, run_id)


@router.delete("/{run_id}", status_code=204)
def delete_run(run_id: int, session: Session = Depends(get_session)) -> None:
    runs_svc.delete_run(session, run_id)


@router.patch("/{run_id}", response_model=RunSummaryOut)
def rename_run(
    run_id: int,
    payload: RunRenameRequest,
    session: Session = Depends(get_session),
) -> EvalRun:
    return runs_svc.rename_run(session, run_id, payload)


@router.post("/{run_id}/pin")
def pin_run(
    run_id: int,
    pinned: bool = Query(..., description="true=置顶保护，false=取消"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return runs_svc.set_run_pinned(session, run_id, pinned)


@router.get("/{run_id}/progress", response_model=ProgressOut)
def get_progress(run_id: int, session: Session = Depends(get_session)) -> ProgressOut:
    run = runs_svc.get_run_or_404(session, run_id)
    snap = get_job_runner().progress_snapshot(run_id)
    return ProgressOut(status=run.status, progress=snap)


@router.get("/{run_id}/diff")
def diff_run(
    run_id: int,
    against: int = Query(..., description="对比的历史 run id"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return runs_svc.diff_runs(session, run_id, against)
