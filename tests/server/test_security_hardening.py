"""B0 安全加固：run_slug 消毒、产物路径边界、生产密钥强校验、上传大小上限。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from medeval.run_slug import make_run_slug
from server.paths import safe_join
from server.settings import get_settings


# --- run_slug 路径消毒 -------------------------------------------------------

def test_make_run_slug_strips_traversal():
    slug = make_run_slug("../../etc/passwd")
    assert "/" not in slug
    assert "\\" not in slug
    assert ".." not in slug


def test_make_run_slug_keeps_normal_label():
    now = datetime(2026, 6, 11, 0, 0, 0)
    slug = make_run_slug("doubao_breast_cancer", now=now)
    assert slug.startswith("doubao_breast_cancer_2026-06-11_")


def test_make_run_slug_keeps_unicode_label():
    # 中文 run 名应保留（不破坏现有中文目录行为），仅去路径危险字符。
    slug = make_run_slug("乳腺癌评测")
    assert slug.startswith("乳腺癌评测_")


# --- safe_join 边界 ----------------------------------------------------------

def test_safe_join_allows_inside(tmp_path: Path):
    target = safe_join(tmp_path, "sub", "report.json")
    assert str(target).startswith(str(tmp_path.resolve()))


def test_safe_join_blocks_escape(tmp_path: Path):
    with pytest.raises(ValueError):
        safe_join(tmp_path, "../outside")


# --- 生产环境会话密钥强校验 --------------------------------------------------

def test_production_default_secret_rejected(monkeypatch):
    monkeypatch.setenv("MEDEVAL_ENV", "production")
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            get_settings().check_production_security()
    finally:
        get_settings.cache_clear()


def test_production_with_strong_secret_ok(monkeypatch):
    monkeypatch.setenv("MEDEVAL_ENV", "production")
    monkeypatch.setenv("SESSION_SECRET", "a-strong-random-secret")
    get_settings.cache_clear()
    try:
        get_settings().check_production_security()  # MUST NOT raise
    finally:
        get_settings.cache_clear()


def test_development_default_secret_ok(monkeypatch):
    monkeypatch.delenv("MEDEVAL_ENV", raising=False)
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    get_settings.cache_clear()
    try:
        get_settings().check_production_security()  # dev 默认值可启动
    finally:
        get_settings.cache_clear()


# --- 上传大小上限 ------------------------------------------------------------

def test_upload_exceeds_limit_rejected(initialized_db, monkeypatch):
    monkeypatch.setenv("MEDEVAL_MAX_UPLOAD_BYTES", "50")
    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from server.app import create_app

    try:
        with TestClient(create_app()) as c:
            big = b"x" * 5000
            resp = c.post(
                "/api/benchmarks",
                files={"file": ("big.yaml", big, "text/yaml")},
                data={"name": "big", "version": "v1"},
            )
            assert resp.status_code == 413, resp.text
    finally:
        get_settings.cache_clear()
