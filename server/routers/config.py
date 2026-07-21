"""评测配置读取路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..services import platform_config as config_service

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/failure-tags")
def failure_tag_labels() -> dict[str, str]:
    return config_service.failure_tag_labels()


@router.get("/judge-verdict-labels")
def judge_verdict_labels() -> dict[str, str]:
    return config_service.judge_verdict_labels()


@router.get("/judge-defaults")
def judge_defaults() -> dict[str, Any]:
    return config_service.judge_defaults()


@router.get("/evaluation-standard")
def evaluation_standard() -> dict[str, Any]:
    """回传固定八维、三端和45分评级口径，供前端展示。"""
    return config_service.evaluation_standard()
