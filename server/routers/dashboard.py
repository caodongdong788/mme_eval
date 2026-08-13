"""dashboard 路由：跨 run 趋势（按 benchmark 维度的时间序列）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_session
from ..services import dashboard as dash_svc

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/trends")
def trends(
    benchmark_id: int = Query(..., description="按该 benchmark 汇总历次 run"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return dash_svc.benchmark_trends(session, benchmark_id)


@router.get("/regression-trends")
def regression_trends(
    scheduled_evaluation_id: int = Query(..., description="定时评测任务 ID"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """仅按指定定时任务串联历次成功 run，供回归趋势看板使用。"""
    return dash_svc.scheduled_regression_trends(session, scheduled_evaluation_id)
