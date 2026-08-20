"""评测配置读取路由。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..auth import require_admin_user
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


def _disable_secret_caching(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


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
def evaluation_accounts(
    _admin: Optional[FeishuUser] = Depends(require_admin_user),
) -> dict[str, Any]:
    return config_service.evaluation_accounts()


@router.get("/evaluation-standard")
def evaluation_standard() -> dict[str, Any]:
    """回传固定八维、三端和45分评级口径，供前端展示。"""
    return config_service.evaluation_standard()


@router.get("/open-api-keys", response_model=list[OpenApiAccessKeyOut])
def list_open_api_keys(
    response: Response,
    session: Session = Depends(get_session),
    _admin: Optional[FeishuUser] = Depends(require_admin_user),
) -> list:
    _disable_secret_caching(response)
    return [
        open_api_config_service.open_api_key_response(row)
        for row in open_api_config_service.list_open_api_keys(session)
    ]


@router.post("/open-api-keys", response_model=OpenApiAccessKeyCreatedOut, status_code=201)
def create_open_api_key(
    payload: OpenApiAccessKeyCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(require_admin_user),
) -> dict:
    _disable_secret_caching(response)
    row, raw_key = open_api_config_service.create_open_api_key(
        session,
        name=payload.name,
        permissions=list(payload.permissions),
        created_by=current_user.name if current_user else None,
    )
    response = open_api_config_service.open_api_key_response(row)
    response["api_key"] = raw_key
    return response


@router.patch("/open-api-keys/{key_id}", response_model=OpenApiAccessKeyOut)
def update_open_api_key(
    key_id: int,
    payload: OpenApiAccessKeyUpdate,
    response: Response,
    session: Session = Depends(get_session),
    _admin: Optional[FeishuUser] = Depends(require_admin_user),
) -> dict:
    _disable_secret_caching(response)
    row = open_api_config_service.update_open_api_key(
        session, key_id, name=payload.name, permissions=list(payload.permissions)
    )
    return open_api_config_service.open_api_key_response(row)


@router.post("/open-api-keys/{key_id}/rotate", response_model=OpenApiAccessKeyCreatedOut)
def rotate_open_api_key(
    key_id: int,
    response: Response,
    session: Session = Depends(get_session),
    _admin: Optional[FeishuUser] = Depends(require_admin_user),
) -> dict:
    _disable_secret_caching(response)
    row, raw_key = open_api_config_service.rotate_open_api_key(session, key_id)
    response = open_api_config_service.open_api_key_response(row)
    response["api_key"] = raw_key
    return response


@router.delete("/open-api-keys/{key_id}", status_code=204)
def delete_open_api_key(
    key_id: int,
    session: Session = Depends(get_session),
    _admin: Optional[FeishuUser] = Depends(require_admin_user),
) -> None:
    open_api_config_service.delete_open_api_key(session, key_id)
