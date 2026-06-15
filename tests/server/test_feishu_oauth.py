"""飞书 OAuth2 纯函数封装测试（mock httpx，不打真实网络）。"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from server import feishu_oauth as fo


def test_build_authorize_url_contains_params():
    url = fo.build_authorize_url(
        app_id="cli_test",
        redirect_uri="http://localhost:5173/api/auth/feishu/callback",
        scope="offline_access drive:drive",
        state="xyz123",
    )
    parsed = urlparse(url)
    assert parsed.netloc == "accounts.feishu.cn"
    assert parsed.path == "/open-apis/authen/v1/authorize"
    q = parse_qs(parsed.query)
    assert q["client_id"] == ["cli_test"]
    assert q["redirect_uri"] == ["http://localhost:5173/api/auth/feishu/callback"]
    assert q["scope"] == ["offline_access drive:drive"]
    assert q["state"] == ["xyz123"]


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def test_exchange_code_posts_and_parses(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = __import__("json").loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "code": 0,
                "access_token": "u-acc",
                "expires_in": 7200,
                "refresh_token": "u-ref",
                "refresh_token_expires_in": 604800,
                "scope": "offline_access drive:drive",
                "token_type": "Bearer",
            },
        )

    monkeypatch.setattr(
        fo, "_client", lambda: httpx.Client(transport=_mock_transport(handler))
    )
    tok = fo.exchange_code(
        app_id="cli_test",
        app_secret="sec",
        code="the_code",
        redirect_uri="http://localhost:5173/api/auth/feishu/callback",
    )
    assert captured["url"] == "https://open.feishu.cn/open-apis/authen/v2/oauth/token"
    assert captured["json"]["grant_type"] == "authorization_code"
    assert captured["json"]["client_id"] == "cli_test"
    assert captured["json"]["client_secret"] == "sec"
    assert captured["json"]["code"] == "the_code"
    assert tok.access_token == "u-acc"
    assert tok.refresh_token == "u-ref"
    assert tok.expires_in == 7200
    assert tok.refresh_token_expires_in == 604800


def test_refresh_posts_grant_type(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = __import__("json").loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "code": 0,
                "access_token": "u-acc2",
                "expires_in": 7200,
                "refresh_token": "u-ref2",
                "refresh_token_expires_in": 604800,
            },
        )

    monkeypatch.setattr(
        fo, "_client", lambda: httpx.Client(transport=_mock_transport(handler))
    )
    tok = fo.refresh_token(app_id="cli_test", app_secret="sec", refresh_token="old-ref")
    assert captured["json"]["grant_type"] == "refresh_token"
    assert captured["json"]["refresh_token"] == "old-ref"
    assert tok.access_token == "u-acc2"
    assert tok.refresh_token == "u-ref2"


def test_get_user_info_uses_bearer(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "open_id": "ou_abc",
                    "name": "曹冬东",
                    "avatar_url": "https://x/y.png",
                },
            },
        )

    monkeypatch.setattr(
        fo, "_client", lambda: httpx.Client(transport=_mock_transport(handler))
    )
    info = fo.get_user_info("u-acc")
    assert captured["auth"] == "Bearer u-acc"
    assert info.open_id == "ou_abc"
    assert info.name == "曹冬东"
    assert info.avatar_url == "https://x/y.png"


def test_error_code_raises(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 20050, "msg": "bad code"})

    monkeypatch.setattr(
        fo, "_client", lambda: httpx.Client(transport=_mock_transport(handler))
    )
    with pytest.raises(fo.FeishuOAuthError):
        fo.exchange_code(
            app_id="x", app_secret="y", code="bad", redirect_uri="http://z"
        )
