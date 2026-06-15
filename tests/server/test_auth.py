"""会话 / 当前用户 / token 自动刷新 + settings.auth_required 测试。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from server import auth
from server import feishu_oauth as fo
from server.models_db import FeishuUser
from server.settings import Settings, get_settings


# --- settings.auth_required 推导 ---

def test_auth_required_off_without_app_id(monkeypatch):
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
    get_settings.cache_clear()
    assert get_settings().auth_required is False
    get_settings.cache_clear()


def test_auth_required_on_with_creds(monkeypatch):
    monkeypatch.setenv("FEISHU_APP_ID", "cli_x")
    monkeypatch.setenv("FEISHU_APP_SECRET", "sec")
    get_settings.cache_clear()
    assert get_settings().auth_required is True
    get_settings.cache_clear()


def _bundle(access="u-acc", refresh="u-ref", exp=7200, rexp=604800):
    return fo.TokenBundle(
        access_token=access,
        expires_in=exp,
        refresh_token=refresh,
        refresh_token_expires_in=rexp,
        scope="offline_access drive:drive",
    )


def _info(open_id="ou_a", name="曹冬东"):
    return fo.UserInfo(open_id=open_id, name=name, avatar_url="http://x/a.png")


# --- upsert / session ---

def test_upsert_user_sets_expiries(session):
    user = auth.upsert_user(session, _info(), _bundle())
    session.commit()
    assert user.open_id == "ou_a"
    assert user.access_token == "u-acc"
    assert user.access_expires_at > datetime.utcnow()
    assert user.refresh_expires_at > user.access_expires_at


def test_upsert_user_updates_existing(session):
    auth.upsert_user(session, _info(), _bundle(access="old"))
    session.commit()
    auth.upsert_user(session, _info(name="新名"), _bundle(access="new"))
    session.commit()
    rows = session.query(FeishuUser).all()
    assert len(rows) == 1
    assert rows[0].access_token == "new"
    assert rows[0].name == "新名"


def test_session_create_resolve_delete(session):
    auth.upsert_user(session, _info(), _bundle())
    session.commit()
    sid = auth.create_session(session, "ou_a", ttl_seconds=3600)
    session.commit()
    user = auth.resolve_session(session, sid)
    assert user is not None and user.open_id == "ou_a"
    auth.delete_session(session, sid)
    session.commit()
    assert auth.resolve_session(session, sid) is None


def test_expired_session_resolves_none(session):
    auth.upsert_user(session, _info(), _bundle())
    session.commit()
    sid = auth.create_session(session, "ou_a", ttl_seconds=-10)  # 已过期
    session.commit()
    assert auth.resolve_session(session, sid) is None


# --- ensure_fresh_token ---

def _settings_with_creds(monkeypatch) -> Settings:
    monkeypatch.setenv("FEISHU_APP_ID", "cli_x")
    monkeypatch.setenv("FEISHU_APP_SECRET", "sec")
    get_settings.cache_clear()
    return get_settings()


def test_ensure_fresh_token_refreshes_when_near_expiry(session, monkeypatch):
    s = _settings_with_creds(monkeypatch)
    user = auth.upsert_user(session, _info(), _bundle())
    # 手动把 access 设为已过期、refresh 仍有效
    user.access_expires_at = datetime.utcnow() - timedelta(seconds=5)
    session.commit()

    called = {}

    def fake_refresh(*, app_id, app_secret, refresh_token):
        called["used"] = refresh_token
        return _bundle(access="u-acc-new", refresh="u-ref-new")

    monkeypatch.setattr(fo, "refresh_token", fake_refresh)
    auth.ensure_fresh_token(session, user, s)
    session.commit()
    assert called["used"] == "u-ref"
    assert user.access_token == "u-acc-new"
    assert user.access_expires_at > datetime.utcnow()
    get_settings.cache_clear()


def test_ensure_fresh_token_raises_when_refresh_expired(session, monkeypatch):
    s = _settings_with_creds(monkeypatch)
    user = auth.upsert_user(session, _info(), _bundle())
    user.access_expires_at = datetime.utcnow() - timedelta(seconds=5)
    user.refresh_expires_at = datetime.utcnow() - timedelta(seconds=5)
    session.commit()

    with pytest.raises(auth.SessionExpired):
        auth.ensure_fresh_token(session, user, s)
    get_settings.cache_clear()


def test_ensure_fresh_token_converts_oauth_error_to_session_expired(session, monkeypatch):
    """飞书拒绝 refresh_token（如 code=20064）→ 视为会话过期，抛 SessionExpired 而非泄漏 500。"""
    s = _settings_with_creds(monkeypatch)
    user = auth.upsert_user(session, _info(), _bundle())
    user.access_expires_at = datetime.utcnow() - timedelta(seconds=5)
    session.commit()

    def fake_refresh(**kwargs):
        raise fo.FeishuOAuthError("飞书 token 接口返回 code=20064 msg=None")

    monkeypatch.setattr(fo, "refresh_token", fake_refresh)
    with pytest.raises(auth.SessionExpired):
        auth.ensure_fresh_token(session, user, s)
    get_settings.cache_clear()


def test_get_current_user_optional_returns_none_on_refresh_failure(session, monkeypatch):
    """optional 依赖遇到刷新失败时清会话并返回 None，绝不向上抛错。"""
    s = _settings_with_creds(monkeypatch)
    user = auth.upsert_user(session, _info(), _bundle())
    user.access_expires_at = datetime.utcnow() - timedelta(seconds=5)
    session.commit()
    sid = auth.create_session(session, "ou_a", ttl_seconds=3600)
    session.commit()

    def fake_refresh(**kwargs):
        raise fo.FeishuOAuthError("飞书 token 接口返回 code=20064 msg=None")

    monkeypatch.setattr(fo, "refresh_token", fake_refresh)

    class _Req:
        cookies = {auth.SESSION_COOKIE: sid}

    assert auth.get_current_user_optional(_Req(), session) is None
    session.commit()  # 请求结束时落库，会话应已被清理
    assert auth.resolve_session(session, sid) is None
    get_settings.cache_clear()


def test_ensure_fresh_token_noop_when_valid(session, monkeypatch):
    s = _settings_with_creds(monkeypatch)
    user = auth.upsert_user(session, _info(), _bundle())
    session.commit()

    def boom(**kwargs):
        raise AssertionError("不应触发刷新")

    monkeypatch.setattr(fo, "refresh_token", boom)
    auth.ensure_fresh_token(session, user, s)  # access 还很新，不刷新
    assert user.access_token == "u-acc"
    get_settings.cache_clear()
