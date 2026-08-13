"""运行看板的不合格用例 AI 归因。"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from ...auth import get_current_user_optional
from ...db import get_session
from ...models_db import AttributionTaskItem, FeishuUser
from ...schemas import AttributionTaskCreate, AttributionTaskOut, CaseAttributionOut
from ...services.case_attribution import (
    generate_case_attribution,
    get_stored_attribution,
)
from ...services import attribution_tasks
from ...services.case_query import case_row_or_404
from ...services.runs import get_run_or_404
from ._router import router


@router.get(
    "/{run_id}/cases/{sample_id}/attribution",
    response_model=CaseAttributionOut,
)
def get_case_attribution(
    run_id: int,
    sample_id: str,
    session: Session = Depends(get_session),
) -> dict:
    get_run_or_404(session, run_id)
    row = case_row_or_404(session, run_id, sample_id)
    return get_stored_attribution(dict(row.detail_json or {}))


@router.post(
    "/{run_id}/cases/{sample_id}/attribution",
    response_model=CaseAttributionOut,
)
async def create_case_attribution(
    run_id: int,
    sample_id: str,
    session: Session = Depends(get_session),
) -> dict:
    run = get_run_or_404(session, run_id)
    row = case_row_or_404(session, run_id, sample_id)
    return await generate_case_attribution(session, run, row)


@router.get("/{run_id}/attribution-tasks", response_model=list[AttributionTaskOut])
def list_case_attribution_tasks(
    run_id: int,
    session: Session = Depends(get_session),
) -> list[dict]:
    get_run_or_404(session, run_id)
    return attribution_tasks.list_attribution_tasks(session, run_id)


@router.post("/{run_id}/attribution-tasks", response_model=AttributionTaskOut, status_code=201)
async def create_case_attribution_task(
    run_id: int,
    payload: AttributionTaskCreate,
    session: Session = Depends(get_session),
    current_user: FeishuUser | None = Depends(get_current_user_optional),
) -> dict:
    run = get_run_or_404(session, run_id)
    task = attribution_tasks.create_attribution_task(
        session,
        run,
        sample_ids=payload.sample_ids,
        judge_model_id=payload.judge_model_id,
        created_by=current_user.name if current_user else None,
    )
    output = attribution_tasks.get_attribution_task(session, run_id, task.id)
    # 事务提交后再开始后台工作，避免 worker 抢在任务/明细对其他会话可见前读取。
    session.commit()
    try:
        attribution_tasks.start_attribution_task(task.id)
    except Exception as exc:
        attribution_tasks.mark_attribution_task_start_failed(task.id, exc)
        raise
    return output


@router.get("/{run_id}/attribution-tasks/{task_id}", response_model=AttributionTaskOut)
def get_case_attribution_task(
    run_id: int,
    task_id: int,
    session: Session = Depends(get_session),
) -> dict:
    return attribution_tasks.get_attribution_task(session, run_id, task_id)


@router.get(
    "/{run_id}/attribution-tasks/{task_id}/cases/{sample_id}/attribution",
    response_model=CaseAttributionOut,
)
def get_case_attribution_task_result(
    run_id: int,
    task_id: int,
    sample_id: str,
    session: Session = Depends(get_session),
) -> dict:
    return attribution_tasks.get_attribution_task_item_result(
        session, run_id, task_id, sample_id
    )


@router.post(
    "/{run_id}/attribution-tasks/{task_id}/rerun",
    response_model=AttributionTaskOut,
    status_code=201,
)
async def rerun_case_attribution_task(
    run_id: int,
    task_id: int,
    session: Session = Depends(get_session),
    current_user: FeishuUser | None = Depends(get_current_user_optional),
) -> dict:
    run = get_run_or_404(session, run_id)
    source = attribution_tasks.get_attribution_task_or_404(session, run_id, task_id)
    sample_ids = [
        item.sample_id
        for item in session.query(AttributionTaskItem)
        .filter_by(task_id=source.id)
        .order_by(AttributionTaskItem.id)
    ]
    task = attribution_tasks.create_attribution_task(
        session,
        run,
        sample_ids=sample_ids,
        judge_model_id=source.judge_model_id,
        created_by=current_user.name if current_user else None,
    )
    output = attribution_tasks.get_attribution_task(session, run_id, task.id)
    session.commit()
    try:
        attribution_tasks.start_attribution_task(task.id)
    except Exception as exc:
        attribution_tasks.mark_attribution_task_start_failed(task.id, exc)
        raise
    return output


@router.delete("/{run_id}/attribution-tasks/{task_id}", status_code=204)
async def delete_case_attribution_task(
    run_id: int,
    task_id: int,
    session: Session = Depends(get_session),
) -> None:
    await attribution_tasks.delete_attribution_task(session, run_id, task_id)
