"""认证路由：飞书 OAuth2 登录 / 回调 / 当前用户 / 退出。"""

from __future__ import annotations

import secrets
from typing import Optional
from urllib.parse import unquote, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import auth as auth_mod
from .. import feishu_oauth as fo
from ..db import get_session
from ..models_db import FeishuUser
from ..settings import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

_STATE_COOKIE = "medeval_oauth_state"
_RETURN_TO_COOKIE = "medeval_oauth_return_to"


def _safe_frontend_path(value: str | None, default: str = "/") -> str:
    """只接受站内相对路径，避免 OAuth 回跳参数形成开放重定向。"""
    if not value:
        return default
    candidate = value.strip()
    decoded_candidate = candidate
    # 同时检查解码后的值，拦截编码或双编码的 //evil.example。
    for _ in range(2):
        decoded = unquote(decoded_candidate)
        if decoded == decoded_candidate:
            break
        decoded_candidate = decoded
    if (
        not decoded_candidate.startswith("/")
        or decoded_candidate.startswith("//")
        or "\\" in decoded_candidate
        or any(ord(char) < 32 for char in decoded_candidate)
    ):
        return default
    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc or parsed.path == "/login":
        return default
    return urlunsplit(("", "", parsed.path or "/", parsed.query, parsed.fragment))


@router.get("/feishu/login")
def feishu_login(redirect_to: Optional[str] = None) -> RedirectResponse:
    settings = get_settings()
    if not settings.feishu_app_id:
        raise HTTPException(status_code=400, detail="未配置飞书应用（FEISHU_APP_ID）")
    state = secrets.token_urlsafe(16)
    url = fo.build_authorize_url(
        app_id=settings.feishu_app_id,
        redirect_uri=settings.feishu_redirect_uri,
        scope=settings.feishu_scopes,
        state=state,
    )
    resp = RedirectResponse(url, status_code=302)
    resp.set_cookie(
        _STATE_COOKIE,
        state,
        httponly=True,
        max_age=600,
        samesite="lax",
        secure=settings.is_production,
    )
    resp.set_cookie(
        _RETURN_TO_COOKIE,
        _safe_frontend_path(redirect_to),
        httponly=True,
        max_age=600,
        samesite="lax",
        secure=settings.is_production,
    )
    return resp


def _frontend_redirect(path: str = "/") -> str:
    base = get_settings().frontend_url.rstrip("/")
    return f"{base}{path}"


@router.get("/feishu/callback")
def feishu_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    settings = get_settings()
    expected_state = request.cookies.get(_STATE_COOKIE, "")
    return_to = _safe_frontend_path(request.cookies.get(_RETURN_TO_COOKIE))

    def _fail(msg: str) -> RedirectResponse:
        resp = RedirectResponse(
            _frontend_redirect(
                "/login?" + urlencode({"error": msg, "redirect_to": return_to})
            ),
            status_code=302,
        )
        resp.delete_cookie(_STATE_COOKIE)
        resp.delete_cookie(_RETURN_TO_COOKIE)
        return resp

    if error:
        return _fail(f"授权被拒绝：{error}")
    if not code:
        return _fail("缺少授权码 code")
    if not state or state != expected_state:
        return _fail("state 校验失败，请重试登录")

    try:
        tok = fo.exchange_code(
            app_id=settings.feishu_app_id,
            app_secret=settings.feishu_app_secret,
            code=code,
            redirect_uri=settings.feishu_redirect_uri,
        )
        info = fo.get_user_info(tok.access_token)
    except fo.FeishuOAuthError as e:
        return _fail(f"获取飞书身份失败：{e}")

    auth_mod.upsert_user(session, info, tok)
    sid = auth_mod.create_session(
        session, info.open_id, ttl_seconds=settings.session_ttl_seconds
    )

    resp = RedirectResponse(_frontend_redirect(return_to), status_code=302)
    resp.delete_cookie(_STATE_COOKIE)
    resp.delete_cookie(_RETURN_TO_COOKIE)
    resp.set_cookie(
        auth_mod.SESSION_COOKIE,
        sid,
        httponly=True,
        max_age=settings.session_ttl_seconds,
        samesite="lax",
        secure=settings.is_production,
    )
    return resp


@router.get("/me")
def me(
    user: Optional[FeishuUser] = Depends(auth_mod.get_current_user_optional),
) -> dict:
    """返回登录态。auth_required=false 时（未配密钥）前端不强制登录。"""
    settings = get_settings()
    payload = {
        "auth_required": settings.auth_required,
        "is_admin": bool(
            not settings.auth_required
            or (user is not None and user.open_id in settings.admin_open_ids)
        ),
        "user": None,
    }
    if user is not None:
        payload["user"] = {
            "open_id": user.open_id,
            "name": user.name,
            "avatar_url": user.avatar_url,
        }
    return payload


@router.post("/logout")
def logout(
    request: Request, session: Session = Depends(get_session)
) -> dict:
    sid = request.cookies.get(auth_mod.SESSION_COOKIE, "")
    auth_mod.delete_session(session, sid)
    from fastapi.responses import JSONResponse

    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth_mod.SESSION_COOKIE)
    return resp
