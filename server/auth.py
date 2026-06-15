"""会话管理、当前用户依赖、per-user token 自动刷新。

设计要点：
- 服务端会话（``user_session`` 表）+ httpOnly cookie，浏览器只持随机 ``session_id``。
- access_token 临过期（剩余 < ``REFRESH_SKEW_SECONDS``）时用 refresh_token 自动续期并回写；
  refresh_token 也过期则抛 :class:`SessionExpired`，上层清会话要求重登。
- 有效期取飞书返回的 ``expires_in`` / ``refresh_token_expires_in``，不硬编码。
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from . import feishu_oauth as fo
from .db import get_session
from .models_db import FeishuUser, UserSession
from .settings import Settings, get_settings

SESSION_COOKIE = "medeval_session"
REFRESH_SKEW_SECONDS = 120


class SessionExpired(RuntimeError):
    """refresh_token 已过期，需要重新登录。"""


def upsert_user(
    session: Session, info: fo.UserInfo, tok: fo.TokenBundle
) -> FeishuUser:
    now = datetime.utcnow()
    user = session.get(FeishuUser, info.open_id)
    if user is None:
        user = FeishuUser(open_id=info.open_id)
        session.add(user)
    user.name = info.name
    user.avatar_url = info.avatar_url
    _apply_token(user, tok, now)
    return user


def _apply_token(user: FeishuUser, tok: fo.TokenBundle, now: datetime) -> None:
    user.access_token = tok.access_token
    user.access_expires_at = now + timedelta(seconds=tok.expires_in)
    if tok.refresh_token:
        user.refresh_token = tok.refresh_token
        user.refresh_expires_at = now + timedelta(seconds=tok.refresh_token_expires_in)
    if tok.scope:
        user.scope = tok.scope


def create_session(session: Session, open_id: str, ttl_seconds: int) -> str:
    sid = secrets.token_urlsafe(32)
    row = UserSession(
        session_id=sid,
        open_id=open_id,
        expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds),
    )
    session.add(row)
    return sid


def resolve_session(session: Session, session_id: str) -> Optional[FeishuUser]:
    if not session_id:
        return None
    row = session.get(UserSession, session_id)
    if row is None or row.expires_at <= datetime.utcnow():
        return None
    return session.get(FeishuUser, row.open_id)


def delete_session(session: Session, session_id: str) -> None:
    row = session.get(UserSession, session_id)
    if row is not None:
        session.delete(row)


def ensure_fresh_token(
    session: Session, user: FeishuUser, settings: Settings
) -> FeishuUser:
    """必要时刷新 access_token；refresh 也过期则抛 SessionExpired。"""
    now = datetime.utcnow()
    exp = user.access_expires_at
    if exp is not None and exp - now > timedelta(seconds=REFRESH_SKEW_SECONDS):
        return user  # access 仍新鲜，无需刷新

    if user.refresh_expires_at is not None and user.refresh_expires_at <= now:
        raise SessionExpired("refresh_token 已过期，请重新登录")
    if not user.refresh_token:
        raise SessionExpired("缺少 refresh_token，请重新登录")

    try:
        tok = fo.refresh_token(
            app_id=settings.feishu_app_id,
            app_secret=settings.feishu_app_secret,
            refresh_token=user.refresh_token,
        )
    except fo.FeishuOAuthError as exc:
        # 飞书侧拒绝 refresh_token（如 code=20064 失效/吊销）：会话已无法续期，
        # 统一视为过期，让上层（optional 依赖清会话返回 None / 需登录端点回 401）优雅降级，
        # 不把 OAuth 异常作为 500 泄漏给任意使用该依赖的接口。
        raise SessionExpired(f"refresh_token 续期失败：{exc}") from exc
    _apply_token(user, tok, now)
    return user


# --- FastAPI 依赖 ---

def get_current_user_optional(
    request: Request, session: Session = Depends(get_session)
) -> Optional[FeishuUser]:
    """解析当前登录用户；无有效会话返回 None（不抛错）。"""
    sid = request.cookies.get(SESSION_COOKIE, "")
    user = resolve_session(session, sid)
    if user is None:
        return None
    try:
        ensure_fresh_token(session, user, get_settings())
    except SessionExpired:
        delete_session(session, sid)
        return None
    return user
