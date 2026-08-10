"""评测配置读取路由。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user_optional
from ..db import get_session
from ..models_db import FeishuUser
from ..schemas import (
    OpenApiAccessKeyCreate,
    OpenApiAccessKeyCreatedOut,
    OpenApiAccessKeyOut,
    OpenApiAccessKeyUpdate,
)
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


@router.get("/open-api-keys", response_model=list[OpenApiAccessKeyOut])
def list_open_api_keys(
    session: Session = Depends(get_session),
) -> list:
    return open_api_config_service.list_open_api_keys(session)


@router.post("/open-api-keys", response_model=OpenApiAccessKeyCreatedOut, status_code=201)
def create_open_api_key(
    payload: OpenApiAccessKeyCreate,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> dict:
    row, _raw_key = open_api_config_service.create_open_api_key(
        session,
        name=payload.name,
        permissions=list(payload.permissions),
        created_by=current_user.name if current_user else None,
    )
    return OpenApiAccessKeyOut.model_validate(row).model_dump()


@router.patch("/open-api-keys/{key_id}", response_model=OpenApiAccessKeyOut)
def update_open_api_key(
    key_id: int,
    payload: OpenApiAccessKeyUpdate,
    session: Session = Depends(get_session),
) -> OpenApiAccessKeyOut:
    return open_api_config_service.update_open_api_key(
        session, key_id, name=payload.name, permissions=list(payload.permissions)
    )


@router.post("/open-api-keys/{key_id}/rotate", response_model=OpenApiAccessKeyCreatedOut)
def rotate_open_api_key(
    key_id: int, session: Session = Depends(get_session)
) -> dict:
    row, _raw_key = open_api_config_service.rotate_open_api_key(session, key_id)
    return OpenApiAccessKeyOut.model_validate(row).model_dump()


@router.delete("/open-api-keys/{key_id}", status_code=204)
def delete_open_api_key(key_id: int, session: Session = Depends(get_session)) -> None:
    open_api_config_service.delete_open_api_key(session, key_id)
