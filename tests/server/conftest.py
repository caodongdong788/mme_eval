"""平台后端测试夹具：每个测试一套隔离的临时 SQLite + uploads/outputs 目录。"""

from __future__ import annotations

import pytest

from server import db as db_mod
from server.settings import get_settings


@pytest.fixture
def settings(tmp_path, monkeypatch):
    """指向临时目录的隔离配置；清 lru_cache 使 get_settings() 返回测试配置。"""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("MEDEVAL_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("MEDEVAL_UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MEDEVAL_OUTPUTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("CX_AGENT_TEST_TOKEN", "test-token")
    # 默认测试保持匿名态（不受本地 .env 注入的飞书密钥影响）。
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
    get_settings.cache_clear()
    db_mod.reset_engine_for_tests()
    s = get_settings()
    yield s
    db_mod.reset_engine_for_tests()
    get_settings.cache_clear()


@pytest.fixture
def initialized_db(settings):
    """建好表的数据库。"""
    db_mod.init_db(settings)
    return settings


@pytest.fixture
def session(initialized_db):
    """一个可用的数据库会话（测试内手动提交）。"""
    maker = db_mod.get_sessionmaker()
    s = maker()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client(initialized_db):
    """FastAPI TestClient（用隔离测试 DB；重置 JobRunner 单例）。"""
    from fastapi.testclient import TestClient

    from server.app import create_app
    from server.jobs import reset_job_runner_for_tests
    from server.online_eval_job import reset_online_eval_job_runner_for_tests

    reset_job_runner_for_tests()
    reset_online_eval_job_runner_for_tests()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_job_runner_for_tests()
    reset_online_eval_job_runner_for_tests()
