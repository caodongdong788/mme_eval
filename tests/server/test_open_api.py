"""外部自动化评测 OpenAPI。"""

from __future__ import annotations

from types import SimpleNamespace

from server.models_db import Benchmark, JudgeModelConfig
from server.settings import get_settings


OPEN_HEADERS = {"X-MME-API-Key": "open-test-key"}


def _enable_open_api(monkeypatch) -> None:
    monkeypatch.setenv("MEDEVAL_OPEN_API_KEY", OPEN_HEADERS["X-MME-API-Key"])
    get_settings.cache_clear()


def test_open_api_is_disabled_without_key(client):
    response = client.get("/api/open/v1/benchmarks")
    assert response.status_code == 503
    assert "尚未启用" in response.json()["detail"]


def test_open_api_lists_resources_and_creates_evaluation(client, session, monkeypatch):
    _enable_open_api(monkeypatch)
    benchmark = Benchmark(
        name="开放接口测试集",
        description="用于 OpenAPI 测试",
        source="offline",
        case_count=3,
        levels=["L2", "L3"],
    )
    judge_model = JudgeModelConfig(
        name="开放接口判分模型",
        provider="openai",
        model="judge-test-model",
        api_key="judge-secret",
    )
    session.add_all([benchmark, judge_model])
    session.commit()

    from server.routers import open_api

    captured: dict = {}

    async def submit(run_id, _job):
        captured["run_id"] = run_id

    def fake_build(*args, **kwargs):
        captured.update(kwargs)

        async def noop(_progress):
            return None

        return noop

    monkeypatch.setattr(open_api, "build_eval_job", fake_build)
    monkeypatch.setattr(
        open_api,
        "get_job_runner",
        lambda: SimpleNamespace(
            submit=submit,
            progress_snapshot=lambda _run_id: None,
            queue_snapshot=lambda _run_id: {"state": "queued", "position": 1},
        ),
    )

    benchmarks = client.get("/api/open/v1/benchmarks", headers=OPEN_HEADERS)
    assert benchmarks.status_code == 200
    assert any(item["id"] == benchmark.id for item in benchmarks.json())

    models = client.get("/api/open/v1/judge-models", headers=OPEN_HEADERS)
    assert models.status_code == 200
    model = next(item for item in models.json() if item["id"] == judge_model.id)
    assert model == {
        "id": judge_model.id,
        "name": "开放接口判分模型",
        "provider": "openai",
        "model": "judge-test-model",
        "has_api_key": True,
    }

    response = client.post(
        "/api/open/v1/evaluations",
        headers=OPEN_HEADERS,
        json={
            "benchmark_id": benchmark.id,
            "name": "OpenAPI 自动化评测",
            "evaluation_mode": "multi_turn",
            "enable_rag": True,
            "repeat": 3,
            "levels": ["L2"],
            "enable_judge": True,
            "judge_model_id": judge_model.id,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["evaluation_mode"] == "multi_turn"
    assert body["repeat"] == 3
    assert body["enable_rag"] is True
    assert body["enable_judge"] is True
    assert body["judge_model_id"] == judge_model.id
    assert body["queue_position"] == 1
    assert captured["run_id"] == body["id"]
    assert captured["levels"] == ["L2"]
    assert captured["repeat"] == 3
    assert captured["adapter_full"]["enable_rag"] is True
    assert captured["adapter_full"]["evaluation_mode"] == "multi_turn"
    assert captured["judge_full"]["enabled"] is True
    assert captured["judge_full"]["model"] == "judge-test-model"
    assert captured["judge_full"]["api_key"] == "judge-secret"

    status = client.get(f"/api/open/v1/evaluations/{body['id']}", headers=OPEN_HEADERS)
    assert status.status_code == 200
    assert status.json()["judge_model_id"] == judge_model.id


def test_open_api_rejects_model_when_judge_is_disabled(client, session, monkeypatch):
    _enable_open_api(monkeypatch)
    benchmark = Benchmark(name="无判分测试集", source="offline")
    session.add(benchmark)
    session.commit()

    response = client.post(
        "/api/open/v1/evaluations",
        headers=OPEN_HEADERS,
        json={
            "benchmark_id": benchmark.id,
            "name": "不应创建",
            "enable_judge": False,
            "judge_model_id": 1,
        },
    )
    assert response.status_code == 422
    assert "不能传 judge_model_id" in response.text


def test_open_api_rejects_invalid_key(client, monkeypatch):
    _enable_open_api(monkeypatch)
    response = client.get("/api/open/v1/benchmarks", headers={"X-MME-API-Key": "wrong"})
    assert response.status_code == 403
