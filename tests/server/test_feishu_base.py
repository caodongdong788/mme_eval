"""飞书 Base 读取客户端（mock httpx，不打真实网络）。"""

from __future__ import annotations

import json

import httpx
import pytest

from server import feishu_base as fb


def test_parse_base_url_extracts_app_table_view():
    coords = fb.parse_base_url(
        "https://p130box8iy5.feishu.cn/base/UcDdbdsnSaHPPMssmXFcj5mdn0c"
        "?table=tblVM7obIwJ5CZhv&view=vewUEKR6gR"
    )

    assert coords.app_token == "UcDdbdsnSaHPPMssmXFcj5mdn0c"
    assert coords.table_id == "tblVM7obIwJ5CZhv"
    assert coords.view_id == "vewUEKR6gR"


def test_fetch_base_records_uses_search_api_and_paginates(monkeypatch):
    seen: list[tuple[str, str, dict[str, str], dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        query = dict(request.url.params)
        body = json.loads(request.content.decode())
        seen.append((request.method, path, query, body))
        assert request.headers["Authorization"] == "Bearer u-token"
        if len(seen) == 1:
            assert query["page_size"] == "500"
            assert body == {"view_id": "vew1"}
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "has_more": True,
                        "page_token": "next",
                        "items": [{"record_id": "rec1", "fields": {"会话标题": "A"}}],
                    },
                },
            )
        assert query["page_token"] == "next"
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "has_more": False,
                    "items": [{"record_id": "rec2", "fields": {"会话标题": "B"}}],
                },
            },
        )

    monkeypatch.setattr(
        fb, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )

    records = fb.fetch_base_records(
        "u-token",
        "https://example.feishu.cn/base/app1?table=tbl1&view=vew1",
    )

    assert [r["record_id"] for r in records] == ["rec1", "rec2"]
    assert seen[0][0] == "POST"
    assert seen[0][1] == "/open-apis/bitable/v1/apps/app1/tables/tbl1/records/search"


def test_fetch_base_records_raises_on_bitable_error(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 1254040, "msg": "not found"})

    monkeypatch.setattr(
        fb, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(fb.FeishuBaseError):
        fb.fetch_base_records(
            "u-token",
            "https://example.feishu.cn/base/app1?table=tbl1",
        )


def test_fetch_base_records_wraps_non_json_response(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>bad gateway</html>")

    monkeypatch.setattr(
        fb, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(fb.FeishuBaseError, match="响应不是合法 JSON"):
        fb.fetch_base_records(
            "u-token",
            "https://example.feishu.cn/base/app1?table=tbl1",
        )


def test_fetch_base_records_wraps_http_status_error(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="bad gateway")

    monkeypatch.setattr(
        fb, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(fb.FeishuBaseError, match="查询飞书 Base 记录失败"):
        fb.fetch_base_records(
            "u-token",
            "https://example.feishu.cn/base/app1?table=tbl1",
        )


def test_fetch_base_records_reports_missing_scope(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "code": 99991679,
                "msg": "Unauthorized",
                "error": {
                    "permission_violations": [
                        {"subject": "base:record:read", "type": "action_privilege_required"}
                    ]
                },
            },
        )

    monkeypatch.setattr(
        fb, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(fb.FeishuBaseError, match="base:record:read"):
        fb.fetch_base_records(
            "u-token",
            "https://example.feishu.cn/base/app1?table=tbl1",
        )
