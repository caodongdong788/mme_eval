"""多密钥 OpenAPI 的生成、授权与撤销服务。"""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import secrets
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models_db import OpenApiAccessKey
from ..secret_codec import decrypt_recoverable_secret, encrypt_recoverable_secret


OPEN_API_PERMISSIONS: dict[str, str] = {
    "benchmarks:read": "读取评测用例集",
    "judge_models:read": "读取判分模型",
    "temporary_evaluations:create": "创建并查询临时单轮评测",
    "evaluations:create": "创建评测任务",
    "evaluations:read": "查询评测任务状态",
    "evaluations:read_all": "查询全部来源的评测任务（管理员集成）",
    "attributions:read": "查询归因任务与 CX-Agent 优化建议",
    "attributions:read_all": "查询全部调用方的归因任务（管理员集成）",
}
_LAST_USED_WRITE_INTERVAL = timedelta(minutes=1)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_permissions(permissions: list[str]) -> list[str]:
    unique = list(dict.fromkeys(permissions))
    invalid = [item for item in unique if item not in OPEN_API_PERMISSIONS]
    if invalid:
        raise HTTPException(status_code=422, detail=f"不支持的 OpenAPI 权限：{', '.join(invalid)}")
    if not unique:
        raise HTTPException(status_code=422, detail="请至少选择一项 OpenAPI 权限")
    return unique


def _new_secret() -> str:
    return f"mme_{secrets.token_urlsafe(32)}"


def _key_or_404(session: Session, key_id: int) -> OpenApiAccessKey:
    row = session.get(OpenApiAccessKey, key_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"OpenAPI Key {key_id} 不存在")
    return row


def list_open_api_keys(session: Session) -> list[OpenApiAccessKey]:
    return list(
        session.execute(select(OpenApiAccessKey).order_by(OpenApiAccessKey.id.desc()))
        .scalars()
        .all()
    )


def open_api_key_response(row: OpenApiAccessKey) -> dict:
    """生成管理员配置接口响应，避免 ORM 可恢复密文被序列化到网络。"""
    return {
        "id": row.id,
        "name": row.name,
        "api_key": decrypt_recoverable_secret(row.api_key),
        "key_prefix": row.key_prefix,
        "permissions": list(row.permissions or []),
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "last_used_at": row.last_used_at,
    }


def create_open_api_key(
    session: Session,
    *,
    name: str,
    permissions: list[str],
    created_by: Optional[str],
) -> tuple[OpenApiAccessKey, str]:
    display_name = name.strip()
    if not display_name:
        raise HTTPException(status_code=422, detail="Key 名称不能为空")
    exists = session.execute(
        select(OpenApiAccessKey.id).where(OpenApiAccessKey.name == display_name)
    ).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail=f"OpenAPI Key 名称「{display_name}」已存在")
    raw_key = _new_secret()
    row = OpenApiAccessKey(
        name=display_name,
        api_key=encrypt_recoverable_secret(raw_key),
        key_prefix=f"{raw_key[:14]}…",
        key_hash=_hash(raw_key),
        permissions=_normalize_permissions(permissions),
        created_by=created_by,
    )
    session.add(row)
    session.flush()
    return row, raw_key


def update_open_api_key(
    session: Session, key_id: int, *, name: str, permissions: list[str]
) -> OpenApiAccessKey:
    row = _key_or_404(session, key_id)
    display_name = name.strip()
    if not display_name:
        raise HTTPException(status_code=422, detail="Key 名称不能为空")
    exists = session.execute(
        select(OpenApiAccessKey.id).where(
            OpenApiAccessKey.name == display_name,
            OpenApiAccessKey.id != key_id,
        )
    ).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail=f"OpenAPI Key 名称「{display_name}」已存在")
    row.name = display_name
    row.permissions = _normalize_permissions(permissions)
    session.flush()
    return row


def rotate_open_api_key(session: Session, key_id: int) -> tuple[OpenApiAccessKey, str]:
    row = _key_or_404(session, key_id)
    raw_key = _new_secret()
    row.api_key = encrypt_recoverable_secret(raw_key)
    row.key_prefix = f"{raw_key[:14]}…"
    row.key_hash = _hash(raw_key)
    row.last_used_at = None
    session.flush()
    return row, raw_key


def delete_open_api_key(session: Session, key_id: int) -> None:
    session.delete(_key_or_404(session, key_id))
    session.flush()


def authorize_open_api_key(
    session: Session, supplied_key: str | None, required_permission: str
) -> OpenApiAccessKey:
    if not supplied_key:
        if not session.execute(select(OpenApiAccessKey.id).limit(1)).first():
            raise HTTPException(status_code=503, detail="OpenAPI 尚未启用，请先创建 API Key")
        raise HTTPException(status_code=401, detail="缺少 X-MME-API-Key")
    row = session.execute(
        select(OpenApiAccessKey).where(OpenApiAccessKey.key_hash == _hash(supplied_key))
    ).scalar_one_or_none()
    if row is None:
        # 正常有效请求只需一次索引查询；仅失败路径补查是否完全未配置，以保持
        # 原有 503（未启用）与 403（Key 无效）的响应语义。
        if not session.execute(select(OpenApiAccessKey.id).limit(1)).first():
            raise HTTPException(status_code=503, detail="OpenAPI 尚未启用，请先创建 API Key")
        raise HTTPException(status_code=403, detail="OpenAPI Key 无效")
    granted = set(row.permissions or [])
    global_permission = (
        f"{required_permission}_all" if required_permission.endswith(":read") else ""
    )
    if required_permission not in granted and global_permission not in granted:
        raise HTTPException(status_code=403, detail="该 OpenAPI Key 没有此接口权限")
    now = datetime.utcnow()
    # last_used_at 仅供管理页观察，不参与鉴权或业务判断。按分钟降采样可避免高频
    # OpenAPI 调用每次都争抢数据库写锁、制造 WAL；展示语义仍是“最近使用”。
    if row.last_used_at is None or now - row.last_used_at >= _LAST_USED_WRITE_INTERVAL:
        row.last_used_at = now
    return row
