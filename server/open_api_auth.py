"""对外 OpenAPI 的 API Key 鉴权。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from .db import get_session
from .models_db import OpenApiAccessKey
from .services.open_api_config import authorize_open_api_key


open_api_key_header = APIKeyHeader(
    name="X-MME-API-Key",
    auto_error=False,
    description="由平台生成并在“参数配置 / Open API”中管理的 API Key",
)


def require_open_api_permission(permission: str):
    """构造带权限检查的 FastAPI 依赖。"""

    def checker(
        supplied_key: Annotated[str | None, Security(open_api_key_header)],
        session: Session = Depends(get_session),
    ) -> OpenApiAccessKey:
        return authorize_open_api_key(session, supplied_key, permission)

    return checker
