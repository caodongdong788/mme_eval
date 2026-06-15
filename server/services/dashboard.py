"""Dashboard 跨 run 趋势聚合。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models_db import EvalRun


def benchmark_trends(session: Session, benchmark_id: int) -> dict[str, Any]:
    runs = list(
        session.execute(
            select(EvalRun)
            .where(EvalRun.benchmark_id == benchmark_id, EvalRun.status == "success")
            .order_by(EvalRun.id.asc())
        ).scalars().all()
    )
    points = []
    for r in runs:
        grading = r.grading or {}
        points.append(
            {
                "run_id": r.id,
                "run_slug": r.run_slug,
                "name": r.name,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "pass_rate": r.pass_rate,
                "total": r.total,
                "passed": r.passed,
                "hard_gate_failed": r.hard_gate_failed,
                "avg_composite": grading.get("avg_composite"),
                "avg_dimension": grading.get("avg_dimension", {}),
                "failure_tag_counter": r.failure_tag_counter or {},
                "stability_distribution": r.stability_distribution or {},
                "pass_rate_ci": r.pass_rate_ci or {},
            }
        )
    return {"benchmark_id": benchmark_id, "points": points}
