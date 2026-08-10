"""参数配置页的多 Key OpenAPI 管理。"""

from __future__ import annotations


def _create_key(client, name: str, permissions: list[str]) -> dict:
    response = client.post(
        "/api/config/open-api-keys",
        json={"name": name, "permissions": permissions},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_open_api_keys_are_multiple_copyable_and_permission_scoped(client):
    benchmark_key = _create_key(
        client,
        "CI 只读",
        ["benchmarks:read"],
    )
    evaluation_key = _create_key(
        client,
        "CI 发起评测",
        ["evaluations:create", "evaluations:read"],
    )

    assert benchmark_key["api_key"].startswith("mme_")
    assert benchmark_key["api_key"].startswith(benchmark_key["key_prefix"].removesuffix("…"))
    assert benchmark_key["api_key"] != evaluation_key["api_key"]

    listed = client.get("/api/config/open-api-keys")
    assert listed.status_code == 200
    listed_by_id = {item["id"]: item for item in listed.json()}
    # 参数配置页面可随时重新获取完整值，从而支持复制，而不是仅首次展示。
    assert listed_by_id[benchmark_key["id"]]["api_key"] == benchmark_key["api_key"]
    assert listed_by_id[evaluation_key["id"]]["permissions"] == [
        "evaluations:create",
        "evaluations:read",
    ]

    allowed = client.get(
        "/api/open/v1/benchmarks",
        headers={"X-MME-API-Key": benchmark_key["api_key"]},
    )
    assert allowed.status_code == 200
    forbidden = client.get(
        "/api/open/v1/judge-models",
        headers={"X-MME-API-Key": benchmark_key["api_key"]},
    )
    assert forbidden.status_code == 403


def test_open_api_key_can_update_rotate_and_delete(client):
    key = _create_key(client, "发布流水线", ["benchmarks:read"])
    old_value = key["api_key"]

    updated = client.patch(
        f"/api/config/open-api-keys/{key['id']}",
        json={"name": "发布流水线（只读）", "permissions": ["judge_models:read"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["api_key"] == old_value
    assert updated.json()["permissions"] == ["judge_models:read"]

    rotated = client.post(f"/api/config/open-api-keys/{key['id']}/rotate")
    assert rotated.status_code == 200, rotated.text
    new_value = rotated.json()["api_key"]
    assert new_value != old_value

    old_key_rejected = client.get(
        "/api/open/v1/judge-models", headers={"X-MME-API-Key": old_value}
    )
    assert old_key_rejected.status_code == 403
    new_key_allowed = client.get(
        "/api/open/v1/judge-models", headers={"X-MME-API-Key": new_value}
    )
    assert new_key_allowed.status_code == 200

    deleted = client.delete(f"/api/config/open-api-keys/{key['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/open/v1/judge-models").status_code == 503
