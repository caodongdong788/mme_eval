"""参数配置中的定时评测任务 API。"""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user_optional
from ..db import get_session
from ..models_db import FeishuUser
from ..schemas import RunSummaryOut, ScheduledEvaluationCreate, ScheduledEvaluationOut, ScheduledEvaluationUpdate
from ..services import scheduled_evaluations as service

router = APIRouter(prefix="/api/scheduled-evaluations", tags=["scheduled-evaluations"])


@router.get("", response_model=list[ScheduledEvaluationOut])
def list_schedules(session: Session = Depends(get_session)) -> list:
    return service.list_scheduled_evaluations(session)


@router.post("", response_model=ScheduledEvaluationOut, status_code=201)
def create_schedule(
    payload: ScheduledEvaluationCreate,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
):
    return service.create_scheduled_evaluation(
        session, payload, created_by=current_user.name if current_user else None
    )


@router.patch("/{task_id}", response_model=ScheduledEvaluationOut)
def update_schedule(
    task_id: int, payload: ScheduledEvaluationUpdate, session: Session = Depends(get_session)
):
    return service.update_scheduled_evaluation(session, task_id, payload)


@router.post("/{task_id}/run", response_model=RunSummaryOut, status_code=201)
async def run_schedule_now(task_id: int) -> object:
    """按定时任务当前配置立即发起一次回归评测。"""
    plan = await service.launch_scheduled_evaluation(task_id)
    return plan.run


@router.delete("/{task_id}", status_code=204)
def delete_schedule(task_id: int, session: Session = Depends(get_session)) -> None:
    service.delete_scheduled_evaluation(session, task_id)
