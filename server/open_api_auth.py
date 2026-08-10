"""对外 OpenAPI 的 API Key 鉴权。"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from .db import get_session
from .services.open_api_config import resolve_open_api_key


open_api_key_header = APIKeyHeader(
    name="X-MME-API-Key",
    auto_error=False,
    description="由平台管理员配置的 OpenAPI Key",
)


def require_open_api_key(
    supplied_key: Annotated[str | None, Security(open_api_key_header)],
    session: Session = Depends(get_session),
) -> None:
    configured_key = resolve_open_api_key(session)
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAPI 尚未启用，请配置 MEDEVAL_OPEN_API_KEY",
        )
    if not supplied_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 X-MME-API-Key",
        )
    if not secrets.compare_digest(supplied_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OpenAPI Key 无效",
        )
