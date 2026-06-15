"""benchmark API：PATCH 改名/描述、内置不可改、空名/未知拒绝。"""

from __future__ import annotations

from server.benchmarks import create_uploaded_benchmark
from server.db import session_scope
from server.models_db import Benchmark

VALID_YAML = b"""
- sample_id: up_001
  scenario: \xe7\x97\x87\xe7\x8a\xb6
  level: L3
  score_profile: red_flag
  turns:
    - role: user
      content: x
""".strip()


def _seed_uploaded(settings) -> int:
    with session_scope() as s:
        bm = create_uploaded_benchmark(
            s, name="原名", content=VALID_YAML, filename="m.yaml",
            description="原描述", settings=settings,
        )
        s.flush()
        return bm.id


def test_patch_updates_name_and_description(client, settings):
    bid = _seed_uploaded(settings)
    resp = client.patch(f"/api/benchmarks/{bid}", json={"name": "新名", "description": "新描述"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "新名" and body["description"] == "新描述"


def test_patch_builtin_forbidden(client, settings):
    # 触发内置注册
    client.get("/api/benchmarks")
    with session_scope() as s:
        builtin = s.execute(
            Benchmark.__table__.select().where(Benchmark.source == "builtin")
        ).first()
        bid = builtin.id
    assert client.patch(f"/api/benchmarks/{bid}", json={"name": "x"}).status_code == 400


def test_patch_empty_name_422(client, settings):
    bid = _seed_uploaded(settings)
    assert client.patch(f"/api/benchmarks/{bid}", json={"name": "   "}).status_code == 422


def test_patch_unknown_404(client, settings):
    assert client.patch("/api/benchmarks/99999", json={"name": "x"}).status_code == 404
