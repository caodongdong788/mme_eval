"""外部自动化评测 OpenAPI。"""

from __future__ import annotations

from types import SimpleNamespace

from server.models_db import Benchmark, EvalRun, JudgeModelConfig


def _open_headers(client, permissions: list[str] | None = None) -> dict[str, str]:
    response = client.post(
        "/api/config/open-api-keys",
        json={
            "name": "OpenAPI 测试 Key",
            "permissions": permissions
            or [
                "benchmarks:read",
                "judge_models:read",
                "evaluations:create",
                "evaluations:read",
            ],
        },
    )
    assert response.status_code == 201, response.text
    return {"X-MME-API-Key": response.json()["api_key"]}


def test_open_api_is_disabled_without_key(client):
    response = client.get("/api/open/v1/benchmarks")
    assert response.status_code == 503
    assert "尚未启用" in response.json()["detail"]


def test_open_api_lists_resources_and_creates_evaluation(
    client, session, monkeypatch, settings
):
    open_headers = _open_headers(client)
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

    benchmarks = client.get("/api/open/v1/benchmarks", headers=open_headers)
    assert benchmarks.status_code == 200
    assert any(item["id"] == benchmark.id for item in benchmarks.json())

    models = client.get("/api/open/v1/judge-models", headers=open_headers)
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
        headers=open_headers,
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
    assert body["result"] is None
    assert body["dashboard_url"] == f"{settings.frontend_url}/runs/{body['id']}"
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

    status = client.get(f"/api/open/v1/evaluations/{body['id']}", headers=open_headers)
    assert status.status_code == 200
    assert status.json()["judge_model_id"] == judge_model.id
    assert status.json()["dashboard_url"] == f"{settings.frontend_url}/runs/{body['id']}"
    assert status.json()["result"] is None

    completed = session.get(EvalRun, body["id"])
    assert completed is not None
    completed.status = "success"
    completed.total = 63
    completed.passed = 48
    completed.pass_rate = 48 / 63
    session.commit()

    completed_status = client.get(
        f"/api/open/v1/evaluations/{body['id']}", headers=open_headers
    )
    assert completed_status.status_code == 200
    assert completed_status.json()["result"] == {
        "total_cases": 63,
        "passed_cases": 48,
        "failed_cases": 15,
        "pass_rate": 48 / 63,
    }


def test_open_api_rejects_model_when_judge_is_disabled(client, session):
    open_headers = _open_headers(client, ["evaluations:create"])
    benchmark = Benchmark(name="无判分测试集", source="offline")
    session.add(benchmark)
    session.commit()

    response = client.post(
        "/api/open/v1/evaluations",
        headers=open_headers,
        json={
            "benchmark_id": benchmark.id,
            "name": "不应创建",
            "enable_judge": False,
            "judge_model_id": 1,
        },
    )
    assert response.status_code == 422
    assert "不能传 judge_model_id" in response.text


def test_open_api_rejects_invalid_key(client):
    _open_headers(client, ["benchmarks:read"])
    response = client.get("/api/open/v1/benchmarks", headers={"X-MME-API-Key": "wrong"})
    assert response.status_code == 403


def test_open_api_reports_config_backed_dashscope_model_as_available(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "server-only-key")
    headers = _open_headers(client, ["judge_models:read"])
    response = client.get("/api/open/v1/judge-models", headers=headers)
    assert response.status_code == 200
    default = next(
        item for item in response.json() if item["name"] == "百炼 DashScope · kimi-k2.6"
    )
    assert default["has_api_key"] is True
