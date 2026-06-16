"""API datetime JSON 序列化：DB 存 UTC naive，响应 MUST 带 Z 供前端转本地时区。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from pydantic import PlainSerializer


def serialize_api_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        aware = value.replace(tzinfo=timezone.utc)
    else:
        aware = value.astimezone(timezone.utc)
    return aware.isoformat().replace("+00:00", "Z")


ApiDateTime = Annotated[
    datetime,
    PlainSerializer(serialize_api_datetime, when_used="json-unless-none"),
]
