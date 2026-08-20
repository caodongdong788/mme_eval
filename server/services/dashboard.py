"""Dashboard 跨 run 趋势聚合。"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, load_only

from ..models_db import EvalRun, ScheduledEvaluation


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
