"""飞书 Sheet/Wiki Sheet 读取客户端（mock httpx，不打真实网络）。"""

from __future__ import annotations

import json

import httpx
import pytest

from server import feishu_sheet as fs


def test_parse_sheet_url_accepts_wiki_and_sheets():
    assert fs.parse_sheet_url(
        "https://p130box8iy5.feishu.cn/wiki/NZTtwSw0zilkcwkxDgMcuOmynye"
    ).spreadsheet_token == "NZTtwSw0zilkcwkxDgMcuOmynye"
    assert fs.parse_sheet_url(
        "https://p130box8iy5.feishu.cn/sheets/sht123"
    ).spreadsheet_token == "sht123"


def test_fetch_sheet_cells_uses_sheet_ai_tools(monkeypatch):
    seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        tool_input = json.loads(str(body["input"]))
        seen.append({"tool_name": body["tool_name"], "input": tool_input})
        assert request.headers["Authorization"] == "Bearer u-token"
        if body["tool_name"] == "get_workbook_structure":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "output": json.dumps({
                            "sheets": [
                                {
                                    "sheet_id": "bdbf75",
                                    "sheet_name": "20260629",
                                    "row_count": 60,
                                    "column_count": 11,
                                    "is_hidden": False,
                                }
                            ]
                        })
                    },
                },
            )
        assert body["tool_name"] == "get_cell_ranges"
        assert tool_input["sheet_id"] == "bdbf75"
        assert tool_input["ranges"] == ["A1:K60"]
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "output": {
                        "ranges": [
                            {
                                "cells": [[{"value": "会话标题"}], [{"value": "图片咨询"}]],
                                "row_indices": [1, 2],
                                "col_indices": ["A"],
                            }
                        ]
                    }
                },
            },
        )

    monkeypatch.setattr(
        fs, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )

    sheet = fs.fetch_sheet_cells(
        "u-token",
        "https://p130box8iy5.feishu.cn/wiki/NZTtwSw0zilkcwkxDgMcuOmynye",
    )

    assert [item["tool_name"] for item in seen] == ["get_workbook_structure", "get_cell_ranges"]
    assert sheet["sheet_id"] == "bdbf75"
    assert sheet["sheet_name"] == "20260629"
    assert sheet["cells"][1][0]["value"] == "图片咨询"


def test_fetch_sheet_cells_wraps_tool_error(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 999, "msg": "denied"})

    monkeypatch.setattr(
        fs, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(fs.FeishuSheetError, match="denied"):
        fs.fetch_sheet_cells(
            "u-token",
            "https://p130box8iy5.feishu.cn/wiki/NZTtwSw0zilkcwkxDgMcuOmynye",
        )


def test_fetch_sheet_cells_reports_missing_scope(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "code": 99991679,
                "msg": "Unauthorized",
                "error": {
                    "permission_violations": [
                        {"subject": "sheets:spreadsheet:read", "type": "action_privilege_required"}
                    ]
                },
            },
        )

    monkeypatch.setattr(
        fs, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(fs.FeishuSheetError, match="sheets:spreadsheet:read"):
        fs.fetch_sheet_cells(
            "u-token",
            "https://p130box8iy5.feishu.cn/wiki/NZTtwSw0zilkcwkxDgMcuOmynye",
        )
