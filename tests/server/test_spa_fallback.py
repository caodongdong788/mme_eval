"""SPA 静态托管：客户端路由回退 index.html。"""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.jobs import reset_job_runner_for_tests
from server.settings import get_settings


@pytest.fixture
def spa_client(tmp_path, initialized_db, monkeypatch):
    """临时 frontend/dist，验证 SPA 回退。"""
    dist = tmp_path / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><html><title>mme-spa-test</title></html>",
        encoding="utf-8",
    )
    assets = dist / "assets"
    assets.mkdir()
    (assets / "main.js").write_text("console.log('ok')", encoding="utf-8")

    custom = replace(get_settings(), project_root=tmp_path)
    monkeypatch.setattr("server.app.get_settings", lambda: custom)

    reset_job_runner_for_tests()
    app = create_app()
    with TestClient(app) as client:
        yield client
    reset_job_runner_for_tests()


def test_spa_fallback_runs_route(spa_client):
    resp = spa_client.get("/runs")
    assert resp.status_code == 200
    assert "mme-spa-test" in resp.text


def test_spa_fallback_nested_route(spa_client):
    resp = spa_client.get("/runs/42/cases/bc_001")
    assert resp.status_code == 200
    assert "mme-spa-test" in resp.text


def test_spa_serves_assets(spa_client):
    resp = spa_client.get("/assets/main.js")
    assert resp.status_code == 200
    assert "console.log" in resp.text


def test_api_health_unaffected(spa_client):
    assert spa_client.get("/api/health").json() == {"status": "ok"}


def test_spa_root(spa_client):
    resp = spa_client.get("/")
    assert resp.status_code == 200
    assert "mme-spa-test" in resp.text
