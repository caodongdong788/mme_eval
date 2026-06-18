"""benchmark 单用例 YAML 读写 API。"""

from __future__ import annotations

from server.benchmarks import ensure_builtin_benchmark
from server.db import session_scope

VALID_ONE = """
- sample_id: up_001
  scenario: 症状
  level: L3
  score_profile: red_flag
  turns:
    - role: user
      content: 我胸口痛
""".strip()


def _seed_uploaded(client, settings) -> int:
    content = (
        "- sample_id: up_001\n  scenario: 症状\n  level: L3\n  turns:\n"
        "    - role: user\n      content: hi\n"
        "- sample_id: up_002\n  scenario: 筛查\n  level: L1\n  turns:\n"
        "    - role: user\n      content: q\n"
    ).encode()
    with session_scope() as s:
        from server.benchmarks import create_uploaded_benchmark

        bm = create_uploaded_benchmark(
            s, name="yaml单条", content=content, filename="t.yaml", settings=settings
        )
        s.flush()
        return bm.id


def test_get_and_save_case_yaml(client, settings):
    bid = _seed_uploaded(client, settings)
    get = client.get(f"/api/benchmarks/{bid}/cases/up_001/yaml")
    assert get.status_code == 200, get.text
    body = get.json()
    assert body["sample_id"] == "up_001"
    assert "up_001" in body["yaml_text"]

    updated = body["yaml_text"].replace("症状", "症状（改）")
    put = client.put(
        f"/api/benchmarks/{bid}/cases/up_001/yaml",
        json={"yaml_text": updated},
    )
    assert put.status_code == 200, put.text
    assert "症状（改）" in put.json()["yaml_text"]

    cases = client.get(f"/api/benchmarks/{bid}/cases").json()
    row = next(c for c in cases if c["sample_id"] == "up_001")
    assert row["scenario"] == "症状（改）"


def test_save_case_yaml_rejects_bad_sample_id(client, settings):
    bid = _seed_uploaded(client, settings)
    get = client.get(f"/api/benchmarks/{bid}/cases/up_001/yaml").json()
    bad = get["yaml_text"].replace("up_001", "other_id")
    resp = client.put(
        f"/api/benchmarks/{bid}/cases/up_001/yaml",
        json={"yaml_text": bad},
    )
    assert resp.status_code == 422


def test_builtin_case_yaml_roundtrip(client, settings):
    with session_scope() as s:
        bm = ensure_builtin_benchmark(s, settings)
        s.flush()
        bid = bm.id
    listed = client.get(f"/api/benchmarks/{bid}/cases").json()
    sid = listed[0]["sample_id"]
    get = client.get(f"/api/benchmarks/{bid}/cases/{sid}/yaml")
    assert get.status_code == 200, get.text
    assert get.json()["case_file"]
