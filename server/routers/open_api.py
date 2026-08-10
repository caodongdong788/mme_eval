"""面向自动化调用方的评测 OpenAPI。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session
from ..jobs import get_job_runner
from ..models_db import EvalRun
from ..open_api_auth import require_open_api_permission
from ..settings import get_settings
from medeval.evaluation_account_limiter import account_queue_snapshot
from ..schemas import (
    AdapterOverride,
    JudgeOverride,
    OpenBenchmarkOut,
    OpenEvaluationCreate,
    OpenEvaluationOut,
    OpenEvaluationResult,
    OpenJudgeModelOut,
    RunCreate,
)
from ..services import benchmark_catalog as benchmark_svc
from ..services import judge_models as judge_models_svc
from ..services import runs as runs_svc
from .runs import build_eval_job


router = APIRouter(
    prefix="/api/open/v1",
    tags=["open-api"],
)


def _as_open_evaluation(run: EvalRun, payload: OpenEvaluationCreate | None = None) -> OpenEvaluationOut:
    adapter = run.adapter_overrides or {}
    judge = run.judge_overrides or {}
    runner = get_job_runner()
    queue_snapshot = getattr(runner, "queue_snapshot", None)
    queue = queue_snapshot(run.id) if callable(queue_snapshot) else {}
    queue = queue or {}
    account_queue = account_queue_snapshot(str(run.id))
    result = (
        OpenEvaluationResult(
            total_cases=run.total,
            passed_cases=run.passed,
            failed_cases=max(run.total - run.passed, 0),
            pass_rate=run.pass_rate,
        )
        if run.status == "success"
        else None
    )
    return OpenEvaluationOut(
        id=run.id,
        dashboard_url=f"{get_settings().frontend_url.rstrip('/')}/runs/{run.id}",
        name=run.name,
        status=run.status,
        benchmark_id=run.benchmark_id or 0,
        evaluation_mode=run.evaluation_mode,
        repeat=run.n_runs or 1,
        enable_rag=bool(adapter.get("enable_rag", False)),
        enable_judge=bool(judge.get("enabled", True)),
        judge_model_id=(
            payload.judge_model_id
            if payload is not None
            else adapter.get("open_api_judge_model_id")
        ),
        result=result,
        progress=runner.progress_snapshot(run.id) or run.progress or None,
        queue_position=queue.get("position"),
        waiting_for_accounts=bool(account_queue.get("waiting_for_accounts", False)),
        account_queue=account_queue,
        error_msg=run.error_msg or "",
    )


@router.get(
    "/benchmarks",
    response_model=list[OpenBenchmarkOut],
    summary="查询可用评测用例集",
    dependencies=[Depends(require_open_api_permission("benchmarks:read"))],
)
def list_open_benchmarks(session: Session = Depends(get_session)) -> list[OpenBenchmarkOut]:
    return [
        OpenBenchmarkOut(
            id=row.id,
            name=row.name,
            description=row.description,
            version=row.version,
            case_count=row.case_count,
            levels=row.levels or [],
            default_evaluation_mode=row.default_evaluation_mode,
        )
        for row in benchmark_svc.list_benchmarks(session)
    ]


@router.get(
    "/judge-models",
    response_model=list[OpenJudgeModelOut],
    summary="查询可用判分模型",
    dependencies=[Depends(require_open_api_permission("judge_models:read"))],
)
def list_open_judge_models(session: Session = Depends(get_session)) -> list[OpenJudgeModelOut]:
    return [
        OpenJudgeModelOut(
            id=row.id,
            name=row.name,
            provider=row.provider,
            model=row.model,
            has_api_key=judge_models_svc.has_judge_model_api_key(row),
        )
        for row in judge_models_svc.list_judge_models(session)
    ]


@router.post(
    "/evaluations",
    response_model=OpenEvaluationOut,
    status_code=201,
    summary="创建评测任务",
    dependencies=[Depends(require_open_api_permission("evaluations:create"))],
)
async def create_open_evaluation(
    payload: OpenEvaluationCreate,
    session: Session = Depends(get_session),
) -> OpenEvaluationOut:
    run_payload = RunCreate(
        benchmark_id=payload.benchmark_id,
        run_name=payload.name,
        evaluation_mode=payload.evaluation_mode,
        levels=payload.levels,
        repeat=payload.repeat,
        judge=JudgeOverride(enabled=payload.enable_judge),
        adapter=AdapterOverride(enable_rag=payload.enable_rag),
        judge_model_id=payload.judge_model_id,
    )
    plan = runs_svc.prepare_create_run(session, run_payload, created_by="OpenAPI")
    # EvalRun 没有单独的 judge_model_id 列；将这个 OpenAPI 入参作为运行元数据保存，
    # 不参与 adapter 配置合并，也不包含任何连接凭据。
    plan.run.adapter_overrides = {
        **(plan.run.adapter_overrides or {}),
        "open_api_judge_model_id": payload.judge_model_id,
    }
    session.commit()
    job = build_eval_job(
        plan.run.id,
        benchmark_id=plan.benchmark_id,
        run_name=plan.run_name,
        levels=plan.levels,
        limit=plan.limit,
        repeat=plan.repeat,
        judge_full=plan.judge_full,
        adapter_full=plan.adapter_full,
    )
    await get_job_runner().submit(plan.run.id, job)
    return _as_open_evaluation(plan.run, payload)


@router.get(
    "/evaluations/{run_id}",
    response_model=OpenEvaluationOut,
    summary="查询评测任务状态",
    dependencies=[Depends(require_open_api_permission("evaluations:read"))],
)
def get_open_evaluation(run_id: int, session: Session = Depends(get_session)) -> OpenEvaluationOut:
    run = session.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"评测任务 {run_id} 不存在")
    return _as_open_evaluation(run)
