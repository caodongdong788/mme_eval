"""面向自动化调用方的评测 OpenAPI。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_session
from ..jobs import get_job_runner
from ..models_db import CaseResultRow, EvalRun
from ..open_api_auth import require_open_api_permission
from ..settings import get_settings
from medeval.evaluation_account_limiter import account_queue_snapshot
from ..schemas import (
    AdapterOverride,
    JudgeOverride,
    OpenBenchmarkOut,
    OpenEvaluationCreate,
    OpenEvaluationBatchItem,
    OpenEvaluationBatchOut,
    OpenEvaluationOut,
    OpenEvaluationGradeResult,
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
        avg_composite=(run.grading or {}).get("avg_composite"),
        avg_dimension=(run.grading or {}).get("avg_dimension", {}),
        stability_distribution=run.stability_distribution or {},
        latency_summary=run.latency_summary or {},
        ttft_summary=run.ttft_summary or {},
        token_summary=run.token_summary or {},
        reliability=(run.grading or {}).get("reliability", {}),
        pass_rate_ci=run.pass_rate_ci or {},
        guideline_match=run.guideline_match or {},
        failure_tag_counter=run.failure_tag_counter or {},
        by_level=run.by_level or {},
        by_scenario=run.by_scenario or {},
        by_case_type=run.by_case_type or {},
    )


def _grade_results_by_run(session: Session, runs: list[EvalRun]) -> dict[int, OpenEvaluationGradeResult]:
    """批量聚合完成任务的最终评级，避免 N 个 run 触发 N 次查询。"""
    completed_ids = [run.id for run in runs if run.status == "success"]
    if not completed_ids:
        return {}
    grouped = session.execute(
        select(CaseResultRow.run_id, CaseResultRow.grade, func.count(CaseResultRow.id))
        .where(CaseResultRow.run_id.in_(completed_ids))
        .group_by(CaseResultRow.run_id, CaseResultRow.grade)
    ).all()
    distributions: dict[int, dict[str, int]] = {}
    for run_id, grade, count in grouped:
        distributions.setdefault(run_id, {})[str(grade or "").strip()] = int(count)

    results: dict[int, OpenEvaluationGradeResult] = {}
    for run in runs:
        if run.status != "success":
            continue
        bucket = distributions.get(run.id, {})
        excellent = bucket.get("优秀", 0)
        good = bucket.get("良好", 0)
        qualified = bucket.get("合格", 0)
        failed = bucket.get("不合格", 0)
        known = excellent + good + qualified + failed
        total = max(int(run.total or 0), sum(bucket.values()))
        results[run.id] = OpenEvaluationGradeResult(
            total_cases=total,
            passed_cases=int(run.passed or 0),
            failed_cases=max(total - int(run.passed or 0), 0),
            pass_rate=float(run.pass_rate or 0),
            excellent_cases=excellent,
            good_cases=good,
            qualified_cases=qualified,
            unqualified_cases=failed,
            other_cases=max(total - known, 0),
        )
    return results


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
    plan = runs_svc.prepare_create_run(
        session, run_payload, created_by="OpenAPI", trigger_type="open_api"
    )
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
    "/evaluations",
    response_model=OpenEvaluationBatchOut,
    summary="按任务类型批量查询评测结果",
    dependencies=[Depends(require_open_api_permission("evaluations:read"))],
)
def list_open_evaluations(
    trigger_type: str | None = Query(
        default=None, description="manual=人工触发，scheduled=定时任务触发，open_api=Open API 触发"
    ),
    status: str | None = Query(default=None, description="可选：pending/running/success/failed"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> OpenEvaluationBatchOut:
    valid_trigger_types = {"manual", "scheduled", "open_api"}
    valid_statuses = {"pending", "running", "success", "failed"}
    if trigger_type is not None and trigger_type not in valid_trigger_types:
        raise HTTPException(status_code=422, detail="trigger_type 必须是 manual、scheduled 或 open_api")
    if status is not None and status not in valid_statuses:
        raise HTTPException(status_code=422, detail="status 必须是 pending、running、success 或 failed")

    stmt = select(EvalRun).order_by(EvalRun.id.desc())
    count_stmt = select(func.count(EvalRun.id))
    if trigger_type is not None:
        stmt = stmt.where(EvalRun.trigger_type == trigger_type)
        count_stmt = count_stmt.where(EvalRun.trigger_type == trigger_type)
    if status is not None:
        stmt = stmt.where(EvalRun.status == status)
        count_stmt = count_stmt.where(EvalRun.status == status)
    total = int(session.scalar(count_stmt) or 0)
    runs = list(session.scalars(stmt.offset(offset).limit(limit)))
    grade_results = _grade_results_by_run(session, runs)
    base_url = get_settings().frontend_url.rstrip("/")
    return OpenEvaluationBatchOut(
        total=total,
        items=[
            OpenEvaluationBatchItem(
                id=run.id,
                name=run.name,
                status=run.status,
                trigger_type=run.trigger_type if run.trigger_type in valid_trigger_types else "manual",
                benchmark_id=run.benchmark_id or 0,
                dashboard_url=f"{base_url}/runs/{run.id}",
                created_at=run.created_at,
                finished_at=run.finished_at,
                result=grade_results.get(run.id),
                error_msg=run.error_msg or "",
            )
            for run in runs
        ],
    )


@router.get(
    "/evaluation-summaries/{run_id}",
    response_model=OpenEvaluationOut,
    summary="查询单个评测任务总览",
    dependencies=[Depends(require_open_api_permission("evaluations:read"))],
)
def get_open_evaluation_summary(
    run_id: int, session: Session = Depends(get_session)
) -> OpenEvaluationOut:
    run = session.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"评测任务 {run_id} 不存在")
    return _as_open_evaluation(run)
