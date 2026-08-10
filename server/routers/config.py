"""评测配置读取路由。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user_optional
from ..db import get_session
from ..models_db import FeishuUser
from ..schemas import OpenApiKeyStatusOut, OpenApiKeyUpdate
from ..services import open_api_config as open_api_config_service
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


@router.get("/evaluation-accounts")
def evaluation_accounts() -> dict[str, Any]:
    return config_service.evaluation_accounts()


@router.get("/evaluation-standard")
def evaluation_standard() -> dict[str, Any]:
    """回传固定八维、三端和45分评级口径，供前端展示。"""
    return config_service.evaluation_standard()


@router.get("/open-api-key", response_model=OpenApiKeyStatusOut)
def open_api_key_status(
    session: Session = Depends(get_session),
) -> dict:
    return open_api_config_service.get_open_api_key_status(session)


@router.put("/open-api-key", response_model=OpenApiKeyStatusOut)
def update_open_api_key(
    payload: OpenApiKeyUpdate,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> dict:
    open_api_config_service.save_open_api_key(
        session,
        payload.api_key,
        updated_by=current_user.name if current_user else None,
    )
    return open_api_config_service.get_open_api_key_status(session)


@router.delete("/open-api-key", status_code=204)
def clear_open_api_key(session: Session = Depends(get_session)) -> None:
    open_api_config_service.clear_open_api_key(session)
