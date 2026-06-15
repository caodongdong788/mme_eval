"""run 改名 API：成功 / 空名 422 / 重名 409 / 未知 404 / 同名自身允许。"""

from __future__ import annotations

from factories import make_report

from server.benchmarks import ensure_builtin_benchmark
from server.db import session_scope
from server.ingest import ingest_report


def _seed_run(settings, run_name: str) -> int:
    with session_scope() as s:
        bm = ensure_builtin_benchmark(s, settings)
        s.flush()
        run = ingest_report(s, make_report(run_name), benchmark_id=bm.id)
        s.flush()
        return run.id


def test_rename_success(client, settings):
    rid = _seed_run(settings, "原始名")
    resp = client.patch(f"/api/runs/{rid}", json={"name": "新名字"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "新名字"
    assert client.get(f"/api/runs/{rid}").json()["name"] == "新名字"


def test_rename_empty_name_422(client, settings):
    rid = _seed_run(settings, "有效名")
    assert client.patch(f"/api/runs/{rid}", json={"name": "   "}).status_code == 422


def test_rename_duplicate_409(client, settings):
    a = _seed_run(settings, "甲")
    b = _seed_run(settings, "乙")
    assert b != a
    resp = client.patch(f"/api/runs/{b}", json={"name": "甲"})
    assert resp.status_code == 409


def test_rename_same_name_self_ok(client, settings):
    rid = _seed_run(settings, "保持不变")
    resp = client.patch(f"/api/runs/{rid}", json={"name": "保持不变"})
    assert resp.status_code == 200, resp.text


def test_rename_unknown_404(client, settings):
    assert client.patch("/api/runs/999999", json={"name": "x"}).status_code == 404
