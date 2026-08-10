"""参数配置页的 OpenAPI Key 读写与鉴权联动。"""

from __future__ import annotations


def test_open_api_key_is_write_only_and_takes_effect_immediately(client):
    before = client.get("/api/config/open-api-key")
    assert before.status_code == 200
    assert before.json()["configured"] is False

    saved = client.put("/api/config/open-api-key", json={"api_key": "page-key-123"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["configured"] is True
    assert saved.json()["source"] == "page"
    assert "page-key-123" not in saved.text

    rejected = client.get("/api/open/v1/benchmarks")
    assert rejected.status_code == 401
    allowed = client.get("/api/open/v1/benchmarks", headers={"X-MME-API-Key": "page-key-123"})
    assert allowed.status_code == 200

    cleared = client.delete("/api/config/open-api-key")
    assert cleared.status_code == 204
    assert client.get("/api/open/v1/benchmarks").status_code == 503
