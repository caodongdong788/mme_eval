"""Dashboard 跨 run 趋势聚合。"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, load_only

from ..models_db import EvalRun, ScheduledEvaluation
from medeval.evaluation import DIMENSION_LABELS, EvaluationDimension


_TREND_COLUMNS = (
    EvalRun.id,
    EvalRun.run_slug,
    EvalRun.name,
    EvalRun.finished_at,
    EvalRun.pass_rate,
    EvalRun.total,
    EvalRun.passed,
    EvalRun.medical_safety_failed,
    EvalRun.grading,
    EvalRun.failure_tag_counter,
    EvalRun.stability_distribution,
    EvalRun.pass_rate_ci,
    EvalRun.latency_summary,
    EvalRun.ttft_summary,
    EvalRun.token_summary,
    EvalRun.by_case_type,
)

_EIGHT_DIMENSIONS = tuple(EvaluationDimension)
_RUN_METRICS_COLUMNS = (
    EvalRun.id,
    EvalRun.total,
    EvalRun.grading,
    EvalRun.by_case_type,
)


def _trend_point(run: EvalRun) -> dict[str, Any]:
    """将一次成功评测转换为可直接用于趋势图的完整观测点。"""
    grading = run.grading or {}
    return {
        "run_id": run.id,
        "run_slug": run.run_slug,
        "name": run.name,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "pass_rate": run.pass_rate,
        "total": run.total,
        "passed": run.passed,
        "medical_safety_failed": run.medical_safety_failed,
        "avg_composite": grading.get("avg_composite"),
        "avg_dimension": grading.get("avg_dimension", {}),
        "failure_tag_counter": run.failure_tag_counter or {},
        "stability_distribution": run.stability_distribution or {},
        "pass_rate_ci": run.pass_rate_ci or {},
        "latency_summary": run.latency_summary or {},
        "ttft_summary": run.ttft_summary or {},
        "token_summary": run.token_summary or {},
        "reliability": grading.get("reliability", {}),
        "by_case_type": run.by_case_type or {},
    }


def benchmark_trends(session: Session, benchmark_id: int) -> dict[str, Any]:
    runs = list(
        session.execute(
            select(EvalRun)
            .options(load_only(*_TREND_COLUMNS))
            .where(EvalRun.benchmark_id == benchmark_id, EvalRun.status == "success")
            .order_by(EvalRun.id.asc())
        ).scalars().all()
    )
    return {"benchmark_id": benchmark_id, "points": [_trend_point(run) for run in runs]}


def scheduled_regression_trends(
    session: Session, scheduled_evaluation_id: int
) -> dict[str, Any]:
    """返回一条定时任务的逐次回归观测点；不混入其它任务或人工 run。"""
    task = session.get(ScheduledEvaluation, scheduled_evaluation_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"定时任务 {scheduled_evaluation_id} 不存在")
    runs = list(
        session.execute(
            select(EvalRun)
            .options(load_only(*_TREND_COLUMNS))
            .where(
                EvalRun.scheduled_evaluation_id == task.id,
                EvalRun.trigger_type == "scheduled",
                EvalRun.status == "success",
            )
            .order_by(EvalRun.id.asc())
        ).scalars().all()
    )
    return {
        "scheduled_evaluation": {
            "id": task.id,
            "name": task.name,
            "benchmark_id": task.benchmark_id,
        },
        "points": [_trend_point(run) for run in runs],
    }


def filtered_runs_metrics(session: Session, run_ids: list[int]) -> dict[str, Any]:
    """汇总当前列表筛选后的已完成评测，避免前端逐条拉取用例明细。"""
    unique_ids = sorted({run_id for run_id in run_ids if isinstance(run_id, int) and run_id > 0})
    if len(unique_ids) > 1000:
        raise HTTPException(status_code=422, detail="一次最多统计 1000 个评测任务")
    if not unique_ids:
        return {
            "completed_run_count": 0,
            "dimension_averages": [],
            "case_type_failure_rates": [],
        }

    runs = list(
        session.execute(
            select(EvalRun)
            .options(load_only(*_RUN_METRICS_COLUMNS))
            .where(EvalRun.id.in_(unique_ids), EvalRun.status == "success")
        )
        .scalars()
        .all()
    )

    dimension_sums = {dimension.value: 0.0 for dimension in _EIGHT_DIMENSIONS}
    dimension_weights = {dimension.value: 0 for dimension in _EIGHT_DIMENSIONS}
    case_types: dict[str, dict[str, int]] = {}

    for run in runs:
        weight = max(int(run.total or 0), 1)
        avg_dimension = (run.grading or {}).get("avg_dimension") or {}
        if isinstance(avg_dimension, dict):
            for dimension in _EIGHT_DIMENSIONS:
                value = avg_dimension.get(dimension.value)
                if isinstance(value, (int, float)):
                    dimension_sums[dimension.value] += float(value) * weight
                    dimension_weights[dimension.value] += weight

        for raw_name, raw_summary in (run.by_case_type or {}).items():
            if not isinstance(raw_summary, dict):
                continue
            total = raw_summary.get("total", 0)
            passed = raw_summary.get("passed", 0)
            if not isinstance(total, (int, float)) or not isinstance(passed, (int, float)):
                continue
            total_int = max(int(total), 0)
            if total_int == 0:
                continue
            passed_int = min(max(int(passed), 0), total_int)
            name = str(raw_name).strip() or "未分类"
            bucket = case_types.setdefault(name, {"total": 0, "passed": 0})
            bucket["total"] += total_int
            bucket["passed"] += passed_int

    dimension_averages = [
        {
            "key": dimension.value,
            "label": DIMENSION_LABELS[dimension],
            "average": (
                round(dimension_sums[dimension.value] / dimension_weights[dimension.value], 3)
                if dimension_weights[dimension.value]
                else None
            ),
            "case_count": dimension_weights[dimension.value],
        }
        for dimension in _EIGHT_DIMENSIONS
    ]
    case_type_failure_rates = [
        {
            "case_type": name,
            "total": values["total"],
            "passed": values["passed"],
            "failed": values["total"] - values["passed"],
            "failure_rate": round((values["total"] - values["passed"]) / values["total"] * 100, 1),
        }
        for name, values in case_types.items()
    ]
    case_type_failure_rates.sort(
        key=lambda item: (-item["failure_rate"], -item["failed"], -item["total"], item["case_type"])
    )
    return {
        "completed_run_count": len(runs),
        "dimension_averages": dimension_averages,
        "case_type_failure_rates": case_type_failure_rates,
    }
