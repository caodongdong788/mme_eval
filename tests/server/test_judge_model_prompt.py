"""判分模型 prompt_template CRUD 与 optimize-prompt。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from medeval.judges.prompt_template import DEFAULT_PROMPT_TEMPLATE

from server.benchmarks import ensure_builtin_benchmark
from server.db import session_scope

_VALID_PROMPT = (
    "JUDGE {conversation} {rubric_text} {tool_context} "
    'JSON scores reasons flags {{"scores":{{}}}}'
)


def _seed_benchmark(settings) -> int:
    with session_scope() as s:
        bm = ensure_builtin_benchmark(s, settings)
        s.flush()
        return bm.id


def test_prompt_template_roundtrip(client, settings):
    resp = client.post(
        "/api/judge-models",
        json={
            "name": "带prompt判官",
            "model": "gpt-test",
            "prompt_template": _VALID_PROMPT,
        },
    )
    assert resp.status_code == 201, resp.text
    mid = resp.json()["id"]
    assert "JUDGE" in resp.json()["prompt_template"]

    listed = client.get("/api/judge-models").json()
    row = next(r for r in listed if r["id"] == mid)
    assert row["prompt_template"].startswith("JUDGE")

    upd = client.patch(
        f"/api/judge-models/{mid}",
        json={"prompt_template": "UPDATED " + _VALID_PROMPT},
    )
    assert upd.status_code == 200
    assert upd.json()["prompt_template"].startswith("UPDATED")


@patch(
    "server.routers.judge_models.optimize_judge_prompt",
    new_callable=AsyncMock,
)
def test_optimize_prompt_endpoint(mock_opt, client, settings):
    mock_opt.return_value = "OPT " + _VALID_PROMPT
    resp = client.post(
        "/api/judge-models/optimize-prompt",
        json={"prompt": "draft prompt"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["optimized_prompt"].startswith("OPT")
    mock_opt.assert_awaited_once_with("draft prompt")


def test_launch_injects_prompt_template(client, settings, monkeypatch):
    bid = _seed_benchmark(settings)
    resp = client.post(
        "/api/judge-models",
        json={
            "name": "inject-prompt",
            "model": "gpt-inject",
            "prompt_template": "INJECT " + _VALID_PROMPT,
        },
    )
    mid = resp.json()["id"]
    captured: dict = {}

    async def _noop(progress):
        return None

    def _fake_build(*args, **kwargs):
        captured.update(kwargs)
        return _noop

    monkeypatch.setattr("server.routers.runs.build_eval_job", _fake_build)
    launch = client.post(
        "/api/runs",
        json={"benchmark_id": bid, "run_name": "prompt-run", "judge_model_id": mid},
    )
    assert launch.status_code == 201, launch.text
    judge = captured.get("judge_full") or {}
    assert judge.get("prompt_template", "").startswith("INJECT")


def test_default_prompt_endpoint(client):
    resp = client.get("/api/judge-models/default-prompt")
    assert resp.status_code == 200, resp.text
    body = resp.json()["prompt_template"]
    assert "{conversation}" in body
    assert body == DEFAULT_PROMPT_TEMPLATE


def test_create_without_prompt_uses_default(client, settings):
    resp = client.post(
        "/api/judge-models",
        json={"name": "默认prompt判官", "model": "gpt-default"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["prompt_template"] == DEFAULT_PROMPT_TEMPLATE


def test_create_rejects_invalid_prompt(client, settings):
    resp = client.post(
        "/api/judge-models",
        json={
            "name": "坏prompt",
            "model": "gpt-bad",
            "prompt_template": "no placeholders scores reasons flags",
        },
    )
    assert resp.status_code == 422, resp.text
