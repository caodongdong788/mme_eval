"""runs CRUD、进度与 diff。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from ...auth import get_current_user_optional
from ...constants import LIST_LIMIT_DEFAULT, LIST_LIMIT_MAX
from ...db import get_session
from ...jobs import commit_and_submit_job, get_job_runner
from medeval.evaluation_account_limiter import account_queue_snapshot
from ...models_db import EvalRun, FeishuUser
from ...schemas import ProgressOut, RunCreate, RunDetailOut, RunRenameRequest, RunSummaryOut
from ...services import attribution_tasks
from ...services import runs as runs_svc
from ._router import router


@router.post("", response_model=RunSummaryOut, status_code=201)
async def create_run(
    payload: RunCreate,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> EvalRun:
    plan = runs_svc.prepare_create_run(
        session,
        payload,
        created_by=current_user.name if current_user else None,
    )
    from . import build_eval_job

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
        session, plan.run.id, job, job_runner=get_job_runner()
    )
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
async def delete_run(run_id: int, session: Session = Depends(get_session)) -> None:
    # 先终止进程内 Job，避免已取消的协程在记录删除后继续回写 Case 结果。
    await get_job_runner().cancel(run_id)
    # 归因任务以独立外键关联评测；先终止模型调用并删除逐 Case 快照，
    # 避免评测删除在事务提交阶段才触发 FK 错误。
    await attribution_tasks.delete_attribution_tasks_for_run(session, run_id)
    runs_svc.delete_run(session, run_id)
    # FastAPI 的依赖事务会在响应生成后提交。这里提前 flush，确保只有数据库
    # 确认可删除时才向前端返回 204，杜绝“页面消失、刷新又出现”。
    session.flush()


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
    runner = get_job_runner()
    snap = runner.progress_snapshot(run_id)
    stored = run.progress if isinstance(run.progress, dict) else {}
    if snap is None:
        snap = dict(stored) or None
    elif isinstance(stored.get("context"), dict):
        snap = {**snap, "context": dict(stored["context"])}
    # 兼容自定义/旧版 JobRunner：队列状态是增强信息，不能影响原有进度查询。
    queue_snapshot = getattr(runner, "queue_snapshot", None)
    queue = queue_snapshot(run_id) if callable(queue_snapshot) else None
    return ProgressOut(
        status=run.status,
        progress=snap,
        queue_position=(queue or {}).get("position"),
        account_queue=account_queue_snapshot(str(run_id)),
    )


@router.get("/{run_id}/diff")
def diff_run(
    run_id: int,
    against: int = Query(..., description="对比的历史 run id"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return runs_svc.diff_runs(session, run_id, against)


@router.get("/{run_id}/release-gate")
def get_release_gate(
    run_id: int,
    baseline_run_id: int = Query(..., description="回归基线 run id"),
    max_pass_rate_drop: float = Query(0.0, ge=0.0, le=1.0),
    max_regressions: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """供 GitLab CI/发布流程调用的确定性回归门禁。"""
    return runs_svc.release_gate(
        session, run_id, baseline_run_id,
        max_pass_rate_drop=max_pass_rate_drop,
        max_regressions=max_regressions,
    )
