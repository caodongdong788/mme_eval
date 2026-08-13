"""判分模型配置中心：CRUD + Key 只写不读 + 发起评测注入。"""

from __future__ import annotations

from server.benchmarks import create_uploaded_benchmark
from server.db import session_scope
from server.models_db import EvalRun, JudgeModelConfig
from server.services.default_judge_model import ensure_default_judge_model


def _seed_benchmark(settings) -> int:
    with session_scope() as s:
        bm = create_uploaded_benchmark(
            s,
            name="v2-test",
            filename="v2.yaml",
            content=(
                '- schema_version: "2.0"\n'
                '  sample_id: v2_test\n'
                '  scenario: test\n'
                '  level: L1\n'
                '  turns:\n'
                '    - role: user\n'
                '      content: test\n'
                '  evaluation: {}\n'
            ).encode(),
            settings=settings,
        )
        s.flush()
        return bm.id


def test_crud_and_key_masking(client, settings):
    # 创建：带 api_key
    resp = client.post(
        "/api/judge-models",
        json={
            "name": "强判官-gpt5",
            "provider": "openai",
            "model": "gpt-5.1",
            "base_url": "https://api.example.com/v1",
            "enable_thinking": False,
            "api_key": "SECRET-KEY",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    mid = body["id"]
    assert body["has_api_key"] is True
    assert body["enable_thinking"] is False
    assert "api_key" not in body  # 只写不读

    # 列表同样不含明文 key
    listed = client.get("/api/judge-models").json()
    row = next(r for r in listed if r["id"] == mid)
    assert row["has_api_key"] is True
    assert "api_key" not in row
    assert row["model"] == "gpt-5.1"

    # 改名 + 不传 key 时保持 has_api_key
    upd = client.patch(f"/api/judge-models/{mid}", json={"name": "强判官-v2"})
    assert upd.status_code == 200, upd.text
    assert upd.json()["name"] == "强判官-v2"
    assert upd.json()["has_api_key"] is True

    # 删除
    assert client.delete(f"/api/judge-models/{mid}").status_code == 204
    assert all(r["id"] != mid for r in client.get("/api/judge-models").json())


def test_default_dashscope_judge_without_runtime_key_is_marked_unavailable(
    client, session, monkeypatch
):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    stored = session.query(JudgeModelConfig).filter_by(
        name="百炼 DashScope · kimi-k2.6"
    ).one()
    stored.api_key = None
    session.commit()
    models = client.get("/api/judge-models").json()
    default = next(m for m in models if m["name"] == "百炼 DashScope · kimi-k2.6")
    assert default["provider"] == "openai"
    assert default["model"] == "kimi-k2.6"
    assert default["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert default["enable_thinking"] is False
    assert default["has_api_key"] is False


def test_default_dashscope_judge_persists_server_env_key_without_exposing_it(
    client, session, settings, monkeypatch
):
    monkeypatch.setenv("LLM_API_KEY", "server-only-key")
    ensure_default_judge_model(session, settings)
    session.commit()
    stored = session.query(JudgeModelConfig).filter_by(
        name="百炼 DashScope · kimi-k2.6"
    ).one()
    assert stored.api_key == "server-only-key"
    models = client.get("/api/judge-models").json()
    default = next(m for m in models if m["name"] == "百炼 DashScope · kimi-k2.6")
    assert default["has_api_key"] is True
    assert "api_key" not in default


def test_config_matching_kimi_model_also_receives_default_key(client, session, settings, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "server-only-key")
    row = JudgeModelConfig(
        name="kimi-k2.6",
        provider="openai",
        model="kimi-k2.6",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=None,
    )
    session.add(row)
    session.commit()

    ensure_default_judge_model(session, settings)
    session.commit()
    assert row.api_key == "server-only-key"


def test_pairwise_concurrency_default_and_update(client, settings):
    # 未提供 → 默认 4
    resp = client.post("/api/judge-models", json={"name": "并发默认", "model": "m"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    mid = body["id"]
    assert body["pairwise_concurrency"] == 4

    # 更新为 8
    upd = client.patch(f"/api/judge-models/{mid}", json={"pairwise_concurrency": 8})
    assert upd.status_code == 200, upd.text
    assert upd.json()["pairwise_concurrency"] == 8

    # 创建时显式指定
    other = client.post(
        "/api/judge-models",
        json={"name": "并发6", "model": "m", "pairwise_concurrency": 6},
    ).json()
    assert other["pairwise_concurrency"] == 6


def test_kimi_k3_model_uses_official_default_configuration(client, settings):
    created = client.post(
        "/api/judge-models",
        json={
            "name": "K3 默认配置",
            "model": "kimi/kimi-k3",
            "temperature": 0.6,
            "enable_thinking": False,
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["temperature"] == 1.0
    assert body["enable_thinking"] is True

    updated = client.patch(
        f"/api/judge-models/{body['id']}",
        json={"temperature": 0.2, "enable_thinking": False},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["temperature"] == 1.0
    assert updated.json()["enable_thinking"] is True


def test_pairwise_concurrency_min_1_422(client, settings):
    resp = client.post(
        "/api/judge-models",
        json={"name": "非法并发", "model": "m", "pairwise_concurrency": 0},
    )
    assert resp.status_code == 422


def test_duplicate_name_409(client, settings):
    base = {"name": "唯一名", "model": "m1"}
    assert client.post("/api/judge-models", json=base).status_code == 201
    assert client.post("/api/judge-models", json=base).status_code == 409


def test_empty_model_422(client, settings):
    resp = client.post("/api/judge-models", json={"name": "无模型", "model": "   "})
    assert resp.status_code == 422


def test_launch_with_judge_model_injects_key_but_not_public(client, settings, monkeypatch):
    bid = _seed_benchmark(settings)

    captured: dict = {}

    async def _noop(progress):
        return None

    def _fake_build(*args, **kwargs):
        captured.update(kwargs)
        return _noop

    monkeypatch.setattr("server.routers.runs.build_eval_job", _fake_build)

    mid = client.post(
        "/api/judge-models",
        json={"name": "注入判官", "provider": "openai", "model": "gpt-judge", "api_key": "INJECT-KEY"},
    ).json()["id"]

    resp = client.post(
        "/api/runs",
        json={"benchmark_id": bid, "run_name": "用配置判官", "judge_model_id": mid},
    )
    assert resp.status_code == 201, resp.text
    rid = resp.json()["id"]

    # 运行期 judge_full 应注入连接信息 + Key
    judge_full = captured.get("judge_full") or {}
    assert judge_full.get("model") == "gpt-judge"
    assert judge_full.get("api_key") == "INJECT-KEY"

    # 但落库的 judge_overrides 不得含明文 Key
    detail = client.get(f"/api/runs/{rid}").json()
    assert detail["judge_overrides"]["model"] == "gpt-judge"
    assert "api_key" not in detail["judge_overrides"]

    # 防御性脱敏：即使历史快照误含凭据，详情 API 也不得回传。
    with session_scope() as s:
        run = s.get(EvalRun, rid)
        assert run is not None
        run.config_snapshot = {
            "judges": {"eight_dimension": {"api_key": "LEAK"}},
            "adapter": {"cx_agent": {"test_token": "LEAK"}},
        }
    public_snapshot = client.get(f"/api/runs/{rid}").json()["config_snapshot"]
    assert "api_key" not in public_snapshot["judges"]["eight_dimension"]
    assert "test_token" not in public_snapshot["adapter"]["cx_agent"]


def test_launch_unknown_judge_model_404(client, settings):
    bid = _seed_benchmark(settings)
    resp = client.post(
        "/api/runs", json={"benchmark_id": bid, "judge_model_id": 987654}
    )
    assert resp.status_code == 404


def test_launch_persists_selected_evaluation_mode(client, settings, monkeypatch):
    bid = _seed_benchmark(settings)

    async def _noop(progress):
        return None

    monkeypatch.setattr("server.routers.runs.build_eval_job", lambda *args, **kwargs: _noop)
    resp = client.post(
        "/api/runs",
        json={
            "benchmark_id": bid,
            "run_name": "动态多轮模式",
            "evaluation_mode": "multi_turn",
        },
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["evaluation_mode"] == "multi_turn"
    detail = client.get(f"/api/runs/{resp.json()['id']}").json()
    assert detail["evaluation_mode"] == "multi_turn"
    assert detail["adapter_overrides"]["evaluation_mode"] == "multi_turn"


def test_launch_persists_rag_toggle(client, settings, monkeypatch):
    bid = _seed_benchmark(settings)

    async def _noop(progress):
        return None

    monkeypatch.setattr("server.routers.runs.build_eval_job", lambda *args, **kwargs: _noop)
    resp = client.post(
        "/api/runs",
        json={
            "benchmark_id": bid,
            "run_name": "开启 RAG 的评测",
            "adapter": {"enable_rag": True},
        },
    )

    assert resp.status_code == 201, resp.text
    detail = client.get(f"/api/runs/{resp.json()['id']}").json()
    assert detail["adapter_overrides"]["enable_rag"] is True


def test_launch_injects_selected_user_simulator_model(client, settings, monkeypatch):
    bid = _seed_benchmark(settings)
    captured: dict = {}

    async def _noop(progress):
        return None

    def _fake_build(*args, **kwargs):
        captured.update(kwargs)
        return _noop

    monkeypatch.setattr("server.routers.runs.build_eval_job", _fake_build)
    model_id = client.post(
        "/api/judge-models",
        json={"name": "语义追问模型", "model": "simulator-model", "api_key": "SIMULATOR-KEY"},
    ).json()["id"]
    resp = client.post(
        "/api/runs",
        json={
            "benchmark_id": bid,
            "run_name": "指定语义模型",
            "evaluation_mode": "multi_turn",
            "user_simulator_model_id": model_id,
        },
    )

    assert resp.status_code == 201, resp.text
    simulator_full = captured["adapter_full"]["user_simulator"]
    assert simulator_full["model"] == "simulator-model"
    assert simulator_full["api_key"] == "SIMULATOR-KEY"
    detail = client.get(f"/api/runs/{resp.json()['id']}").json()
    assert detail["adapter_overrides"]["user_simulator"]["model"] == "simulator-model"
    assert "api_key" not in detail["adapter_overrides"]["user_simulator"]
