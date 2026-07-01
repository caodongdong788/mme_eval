"""线上评测路由：真实线上对话的 10 分制质检。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..auth import get_current_user_optional
from ..constants import LIST_LIMIT_DEFAULT, LIST_LIMIT_MAX
from ..db import get_session
from ..models_db import FeishuUser, OnlineEval
from ..online_eval_job import get_online_eval_job_runner
from ..schemas import (
    OnlineEvalCreate,
    OnlineEvalDetailOut,
    OnlineEvalExportOut,
    OnlineEvalOut,
    ProgressOut,
)
from ..services.online_eval_export import export_online_eval_cases, split_filter_values
from ..services import online_evals as svc

router = APIRouter(prefix="/api/online-evals", tags=["online-evals"])


@router.post("", response_model=OnlineEvalOut, status_code=201)
async def create_online_eval(
    payload: OnlineEvalCreate,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> OnlineEval:
    row = svc.prepare_online_eval(
        session, payload, created_by=current_user.name if current_user else None
    )
    await get_online_eval_job_runner().submit(row.id)
    return row


@router.get("", response_model=list[OnlineEvalOut])
def list_online_evals(
    limit: int = Query(
        LIST_LIMIT_DEFAULT, ge=1, le=LIST_LIMIT_MAX, description="分页大小"
    ),
    offset: int = Query(0, ge=0, description="分页偏移"),
    session: Session = Depends(get_session),
) -> list[OnlineEval]:
    return svc.list_online_evals(session, limit=limit, offset=offset)


@router.get("/{eval_id}", response_model=OnlineEvalDetailOut)
def get_online_eval(eval_id: int, session: Session = Depends(get_session)) -> OnlineEval:
    return svc.get_online_eval_detail(session, eval_id)


@router.get("/{eval_id}/progress", response_model=ProgressOut)
def get_online_eval_progress(
    eval_id: int,
    session: Session = Depends(get_session),
) -> ProgressOut:
    row = svc.get_online_eval_or_404(session, eval_id)
    return ProgressOut(status=row.status, progress=row.progress or None)


@router.post("/{eval_id}/export-cases", response_model=OnlineEvalExportOut)
def export_online_eval_cases_route(
    eval_id: int,
    gate_status: Optional[str] = Query(None, description="Gate 筛选，逗号分隔"),
    score_bucket: Optional[str] = Query(None, description="分数区间筛选，逗号分隔"),
    grade: Optional[str] = Query(None, description="评级筛选，逗号分隔"),
    parent_folder_token: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> dict[str, Any]:
    return export_online_eval_cases(
        session,
        eval_id,
        gate_statuses=split_filter_values(gate_status),
        score_buckets=split_filter_values(score_bucket),
        grades=split_filter_values(grade),
        parent_folder_token=parent_folder_token,
        current_user=current_user,
    )


@router.delete("/{eval_id}", status_code=204)
def delete_online_eval(eval_id: int, session: Session = Depends(get_session)) -> Response:
    svc.delete_online_eval(session, eval_id)
    return Response(status_code=204)
