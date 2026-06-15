"""认证路由 + 强制登录守卫接口测试。"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from server import db as db_mod
from server import feishu_oauth as fo
from server.settings import get_settings


@pytest.fixture
def auth_settings(tmp_path, monkeypatch):
    """配齐飞书密钥（auth_required=True）+ 隔离 DB。"""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("MEDEVAL_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("MEDEVAL_UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MEDEVAL_OUTPUTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("FEISHU_APP_ID", "cli_test")
    monkeypatch.setenv("FEISHU_APP_SECRET", "sec")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")
    get_settings.cache_clear()
    db_mod.reset_engine_for_tests()
    s = get_settings()
    db_mod.init_db(s)
    yield s
    db_mod.reset_engine_for_tests()
    get_settings.cache_clear()


@pytest.fixture
def auth_client(auth_settings):
    from fastapi.testclient import TestClient

    from server.app import create_app
    from server.jobs import reset_job_runner_for_tests

    reset_job_runner_for_tests()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_job_runner_for_tests()


def test_login_redirects_to_feishu(auth_client):
    resp = auth_client.get("/api/auth/feishu/login", follow_redirects=False)
    assert resp.status_code == 302
    loc = resp.headers["location"]
    parsed = urlparse(loc)
    assert parsed.netloc == "accounts.feishu.cn"
    q = parse_qs(parsed.query)
    assert q["client_id"] == ["cli_test"]
    assert "state" in q


def test_callback_creates_session(auth_client, monkeypatch):
    # 先 login 拿到 state cookie
    login = auth_client.get("/api/auth/feishu/login", follow_redirects=False)
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]

    monkeypatch.setattr(
        fo,
        "exchange_code",
        lambda **k: fo.TokenBundle("u-acc", 7200, "u-ref", 604800, "drive:drive"),
    )
    monkeypatch.setattr(
        fo,
        "get_user_info",
        lambda t: fo.UserInfo("ou_me", "曹冬东", "http://x/a.png"),
    )

    resp = auth_client.get(
        f"/api/auth/feishu/callback?code=abc&state={state}", follow_redirects=False
    )
    assert resp.status_code == 302
    assert resp.headers["location"].startswith("http://localhost:5173")

    me = auth_client.get("/api/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["auth_required"] is True
    assert body["user"]["open_id"] == "ou_me"
    assert body["user"]["name"] == "曹冬东"


def test_callback_bad_state_redirects_login(auth_client, monkeypatch):
    auth_client.get("/api/auth/feishu/login", follow_redirects=False)
    called = {"exchanged": False}

    def _boom(**k):
        called["exchanged"] = True
        raise AssertionError

    monkeypatch.setattr(fo, "exchange_code", _boom)
    resp = auth_client.get(
        "/api/auth/feishu/callback?code=abc&state=WRONG", follow_redirects=False
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]
    assert called["exchanged"] is False


def test_me_anonymous(auth_client):
    resp = auth_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["user"] is None


def test_logout_clears_session(auth_client, monkeypatch):
    login = auth_client.get("/api/auth/feishu/login", follow_redirects=False)
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    monkeypatch.setattr(
        fo, "exchange_code", lambda **k: fo.TokenBundle("u-acc", 7200, "u-ref", 604800)
    )
    monkeypatch.setattr(fo, "get_user_info", lambda t: fo.UserInfo("ou_me", "x"))
    auth_client.get(
        f"/api/auth/feishu/callback?code=abc&state={state}", follow_redirects=False
    )
    assert auth_client.get("/api/auth/me").json()["user"]["open_id"] == "ou_me"

    auth_client.post("/api/auth/logout")
    assert auth_client.get("/api/auth/me").json()["user"] is None


# --- 守卫：强制登录 ---

def test_guard_blocks_protected_when_logged_out(auth_client):
    resp = auth_client.get("/api/benchmarks")
    assert resp.status_code == 401


def test_guard_allows_health_and_auth(auth_client):
    assert auth_client.get("/api/health").status_code == 200
    assert auth_client.get("/api/auth/me").status_code == 200


def test_guard_allows_protected_when_logged_in(auth_client, monkeypatch):
    login = auth_client.get("/api/auth/feishu/login", follow_redirects=False)
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    monkeypatch.setattr(
        fo, "exchange_code", lambda **k: fo.TokenBundle("u-acc", 7200, "u-ref", 604800)
    )
    monkeypatch.setattr(fo, "get_user_info", lambda t: fo.UserInfo("ou_me", "x"))
    auth_client.get(
        f"/api/auth/feishu/callback?code=abc&state={state}", follow_redirects=False
    )
    assert auth_client.get("/api/benchmarks").status_code == 200


def test_no_guard_when_auth_off(client):
    # 默认 client 未配密钥 → auth_required False → 受保护接口可匿名访问
    assert client.get("/api/benchmarks").status_code == 200


def _login(auth_client, monkeypatch):
    login = auth_client.get("/api/auth/feishu/login", follow_redirects=False)
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    monkeypatch.setattr(
        fo, "exchange_code", lambda **k: fo.TokenBundle("u-acc", 7200, "u-ref", 604800)
    )
    monkeypatch.setattr(fo, "get_user_info", lambda t: fo.UserInfo("ou_me", "曹冬东"))
    auth_client.get(
        f"/api/auth/feishu/callback?code=abc&state={state}", follow_redirects=False
    )


def test_export_uses_logged_in_user_token(auth_client, auth_settings, monkeypatch):
    from factories import make_report
    from server.db import session_scope
    from server.ingest import ingest_report
    from server.routers import runs as runs_router

    _login(auth_client, monkeypatch)

    with session_scope() as s:
        run = ingest_report(s, make_report("exprun"))
        s.flush()
        rid = run.id

    captured = {}

    def fake_import(access_token, xlsx_path, *, folder_token, title):
        captured["token"] = access_token
        captured["folder"] = folder_token
        return "https://feishu.cn/sheets/ok"

    monkeypatch.setattr(runs_router, "import_xlsx_as_sheet", fake_import)

    resp = auth_client.post(
        f"/api/runs/{rid}/export-transcripts",
        params={"parent_folder_token": "fld_x"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["url"] == "https://feishu.cn/sheets/ok"
    assert captured["token"] == "u-acc"  # 用的是登录用户 token
    assert captured["folder"] == "fld_x"
