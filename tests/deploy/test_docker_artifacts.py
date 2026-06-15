"""Docker 部署产物存在性与关键契约（不依赖本机安装 Docker 跑 build）。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_dockerfile_exists_and_multistage():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "frontend-build" in text
    assert "uvicorn" in text
    assert "HEALTHCHECK" in text


def test_docker_compose_has_app_db_volumes():
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "services:" in text
    assert "app:" in text
    assert "db:" in text
    assert "mme-data:" in text
    assert "pgdata:" in text
    assert "postgresql" in text


def test_dockerignore_excludes_runtime_artifacts():
    text = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "outputs" in text
    assert ".env" in text
    assert "frontend/node_modules" in text


def test_env_docker_example_documents_production():
    text = (ROOT / ".env.docker.example").read_text(encoding="utf-8")
    assert "MEDEVAL_ENV=production" in text
    assert "SESSION_SECRET" in text
    assert "MEDEVAL_DATABASE_URL" in text


def test_pyproject_postgres_extra():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "psycopg2-binary" in text
