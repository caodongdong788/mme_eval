"""判分模型配置中心：CRUD + Key 只写不读 + 发起评测注入。"""

from __future__ import annotations

from server.benchmarks import ensure_builtin_benchmark
from server.db import session_scope


def _seed_builtin(settings) -> int:
    with session_scope() as s:
        bm = ensure_builtin_benchmark(s, settings)
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
            "api_key": "SECRET-KEY",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    mid = body["id"]
    assert body["has_api_key"] is True
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
    bid = _seed_builtin(settings)

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


def test_launch_unknown_judge_model_404(client, settings):
    bid = _seed_builtin(settings)
    resp = client.post(
        "/api/runs", json={"benchmark_id": bid, "judge_model_id": 987654}
    )
    assert resp.status_code == 404
