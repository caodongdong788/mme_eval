"""benchmark API：PATCH 改名/描述、内置不可改、空名/未知拒绝。"""

from __future__ import annotations

from server.benchmarks import create_uploaded_benchmark
from server.auth import get_current_user_optional
from server.db import session_scope
from server.models_db import Benchmark, FeishuUser

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


def test_upload_online_jsonl_api(client):
    content = (
        '{"序号":"28","会话标题":"线上问题","用户输入内容":"治疗期间怎么运动？",'
        '"Cx输出内容":"可以先从低强度抗阻训练开始。","是否点踩":"Y"}\n'
    ).encode("utf-8")
    resp = client.post(
        "/api/benchmarks",
        data={"name": "线上 JSONL", "description": "线上真实问题", "source": "online"},
        files={"file": ("20260629.jsonl", content, "application/jsonl")},
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["source"] == "online"
    assert body["case_count"] == 1

    cases = client.get(f"/api/benchmarks/{body['id']}/cases")
    assert cases.status_code == 200
    assert cases.json()[0]["sample_id"] == "online_28"


def test_upload_online_feishu_url_api(client, monkeypatch):
    from server import feishu_base

    def fake_fetch(access_token: str, source_url: str):
        assert access_token == "u-token"
        assert source_url == "https://example.feishu.cn/base/app?table=tbl&view=vew"
        return [
            {
                "record_id": "rec_url",
                "fields": {
                    "会话标题": "URL 导入",
                    "第一轮用户输入": "第一问",
                    "第一轮Cx输出": "第一答",
                    "第二轮用户输入": "第二问",
                    "第二轮Cx输出": "第二答",
                },
            }
        ]

    monkeypatch.setattr(feishu_base, "fetch_base_records", fake_fetch)
    client.app.dependency_overrides[get_current_user_optional] = lambda: FeishuUser(
        open_id="ou_test", name="测试用户", access_token="u-token"
    )
    try:
        resp = client.post(
            "/api/benchmarks",
            data={
                "name": "线上 Base URL",
                "description": "从飞书导入",
                "source": "online",
                "source_url": "https://example.feishu.cn/base/app?table=tbl&view=vew",
            },
        )
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["source"] == "online"
    assert body["case_count"] == 1

    cases = client.get(f"/api/benchmarks/{body['id']}/cases").json()
    assert cases[0]["sample_id"] == "online_rec_url"


def test_upload_online_feishu_wiki_sheet_url_api(client, monkeypatch):
    from server import feishu_sheet

    def fake_fetch(access_token: str, source_url: str):
        assert access_token == "u-token"
        assert source_url == "https://example.feishu.cn/wiki/sht_token"
        return {
            "sheet_id": "bdbf75",
            "sheet_name": "20260629",
            "row_indices": [1, 9],
            "cells": [
                [{"value": "会话标题"}, {"value": "第一轮用户输入"}, {"value": "第一轮Cx输出"}],
                [
                    {"value": "图片咨询"},
                    {
                        "rich_text": [
                            {
                                "type": "embed-image",
                                "image_token": "RKuObri3Wob9j5x8Nk4cHEk1nOh",
                                "image_width": 739,
                                "image_height": 1600,
                            }
                        ]
                    },
                    {"value": "报告解读"},
                ],
            ],
        }

    monkeypatch.setattr(feishu_sheet, "fetch_sheet_cells", fake_fetch)
    client.app.dependency_overrides[get_current_user_optional] = lambda: FeishuUser(
        open_id="ou_test", name="测试用户", access_token="u-token"
    )
    try:
        resp = client.post(
            "/api/benchmarks",
            data={
                "name": "线上 Wiki Sheet URL",
                "description": "从飞书 Wiki 表格导入",
                "source": "online",
                "source_url": "https://example.feishu.cn/wiki/sht_token",
            },
        )
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["source"] == "online"
    assert body["case_count"] == 1

    yaml_resp = client.get(f"/api/benchmarks/{body['id']}/cases/online_20260629_9/yaml")
    assert "image_token=RKuObri3Wob9j5x8Nk4cHEk1nOh" in yaml_resp.json()["yaml_text"]


def test_upload_online_feishu_url_requires_login(client):
    resp = client.post(
        "/api/benchmarks",
        data={
            "name": "未登录 Base URL",
            "source": "online",
            "source_url": "https://example.feishu.cn/base/app?table=tbl",
        },
    )

    assert resp.status_code == 401


def test_feishu_image_proxy_requires_login(client):
    resp = client.get("/api/benchmarks/feishu-images/Rhb9bkUUfoA7rSxq4YzcVTT8nAs")

    assert resp.status_code == 401


def test_feishu_image_proxy_downloads_with_user_token(client, monkeypatch):
    from server import feishu_media

    def fake_fetch(access_token: str, image_token: str):
        assert access_token == "u-token"
        assert image_token == "Rhb9bkUUfoA7rSxq4YzcVTT8nAs"
        return feishu_media.FeishuMedia(content=b"jpg", content_type="image/jpeg")

    monkeypatch.setattr(feishu_media, "fetch_media", fake_fetch)
    client.app.dependency_overrides[get_current_user_optional] = lambda: FeishuUser(
        open_id="ou_test", name="测试用户", access_token="u-token"
    )
    try:
        resp = client.get("/api/benchmarks/feishu-images/Rhb9bkUUfoA7rSxq4YzcVTT8nAs")
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content == b"jpg"
