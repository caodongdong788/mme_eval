"""OpenAPI 密钥的运行期配置服务（只写不读）。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from ..models_db import OpenApiKeyConfig
from ..settings import get_settings


def _db_config(session: Session) -> OpenApiKeyConfig | None:
    return session.get(OpenApiKeyConfig, 1)


def resolve_open_api_key(session: Session) -> str:
    """返回当前校验用密钥；数据库配置优先于环境变量。"""
    row = _db_config(session)
    if row is not None and row.api_key.strip():
        return row.api_key.strip()
    return get_settings().open_api_key.strip()


def get_open_api_key_status(session: Session) -> dict:
    row = _db_config(session)
    if row is not None and row.api_key.strip():
        return {
            "configured": True,
            "source": "page",
            "updated_by": row.updated_by,
            "updated_at": row.updated_at,
        }
    configured = bool(get_settings().open_api_key.strip())
    return {
        "configured": configured,
        "source": "environment" if configured else "none",
        "updated_by": None,
        "updated_at": None,
    }


def save_open_api_key(
    session: Session, api_key: str, *, updated_by: Optional[str]
) -> OpenApiKeyConfig:
    value = api_key.strip()
    row = _db_config(session)
    if row is None:
        row = OpenApiKeyConfig(id=1, api_key=value, updated_by=updated_by)
        session.add(row)
    else:
        row.api_key = value
        row.updated_by = updated_by
    session.flush()
    return row


def clear_open_api_key(session: Session) -> None:
    """删除页面覆盖值；若存在环境变量，将自动回退到环境变量。"""
    row = _db_config(session)
    if row is not None:
        session.delete(row)
        session.flush()
