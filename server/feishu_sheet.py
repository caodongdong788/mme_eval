"""以用户 ``user_access_token`` 读取飞书 Sheet / Wiki Sheet 单元格。"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.parse import urlparse

import httpx

_BASE = "https://open.feishu.cn/open-apis/sheet_ai/v2"
_TIMEOUT = 60.0
_MAX_CHARS = 500_000


class FeishuSheetError(RuntimeError):
    """读取飞书 Sheet 失败。"""


@dataclass(frozen=True)
class SheetCoords:
    spreadsheet_token: str


def _client() -> httpx.Client:
    return httpx.Client(timeout=_TIMEOUT)


def parse_sheet_url(url: str) -> SheetCoords:
    parsed = urlparse((url or "").strip())
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2 or parts[0] not in {"wiki", "sheets", "spreadsheets"}:
        raise FeishuSheetError("飞书 URL 需为 /wiki/<token>、/sheets/<token> 或 /spreadsheets/<token> 形式")
    token = parts[1].strip()
    if not token:
        raise FeishuSheetError("飞书 Sheet URL 缺少 spreadsheet token")
    return SheetCoords(spreadsheet_token=token)


def is_sheet_url(url: str) -> bool:
    try:
        parse_sheet_url(url)
    except FeishuSheetError:
        return False
    return True


def _col_name(index: int) -> str:
    name = ""
    while index > 0:
        index, rem = divmod(index - 1, 26)
        name = chr(ord("A") + rem) + name
    return name or "A"


def _check(data: dict[str, Any], what: str) -> dict[str, Any]:
    if data.get("code", 0) != 0:
        raise FeishuSheetError(_format_feishu_error(data, what))
    payload = data.get("data", {})
    if not isinstance(payload, dict):
        return {}
    output = payload.get("output") or payload.get("result") or payload.get("tool_result")
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError as exc:
            raise FeishuSheetError(f"{what} 失败：工具响应不是合法 JSON") from exc
        return parsed if isinstance(parsed, dict) else {}
    if isinstance(output, dict):
        return output
    return payload


def _format_feishu_error(data: dict[str, Any], what: str) -> str:
    code = data.get("code")
    msg = str(data.get("msg") or "")
    violations = data.get("error", {}).get("permission_violations", [])
    scopes = [
        str(item.get("subject"))
        for item in violations
        if isinstance(item, dict) and item.get("subject")
    ]
    if scopes:
        return (
            f"{what} 失败：缺少飞书授权 {', '.join(scopes)}，"
            "请退出后重新飞书登录并授权后重试"
        )
    return f"{what} 失败：code={code} msg={msg}"


def _invoke_read(
    client: httpx.Client,
    access_token: str,
    spreadsheet_token: str,
    tool_name: str,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    endpoint = f"{_BASE}/spreadsheets/{spreadsheet_token}/tools/invoke_read"
    try:
        resp = client.post(
            endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "tool_name": tool_name,
                "input": json.dumps(tool_input, ensure_ascii=False),
            },
        )
        payload = resp.json()
    except httpx.HTTPError as exc:
        raise FeishuSheetError(f"读取飞书 Sheet 失败：{exc}") from exc
    except ValueError as exc:
        raise FeishuSheetError("读取飞书 Sheet 失败：响应不是合法 JSON") from exc
    if resp.status_code >= 400:
        raise FeishuSheetError(_format_feishu_error(payload, f"调用飞书 Sheet 工具 {tool_name}"))
    return _check(payload, f"调用飞书 Sheet 工具 {tool_name}")


def fetch_sheet_cells(access_token: str, url: str) -> dict[str, Any]:
    """读取 URL 指定 Wiki/Sheet 的第一张可见工作表单元格。"""
    coords = parse_sheet_url(url)
    if not access_token:
        raise FeishuSheetError("缺少飞书 user_access_token")

    with _client() as client:
        workbook = _invoke_read(
            client,
            access_token,
            coords.spreadsheet_token,
            "get_workbook_structure",
            {"excel_id": coords.spreadsheet_token},
        )
        sheets = workbook.get("sheets") or []
        sheet = next((item for item in sheets if not item.get("is_hidden")), None)
        if not isinstance(sheet, dict):
            raise FeishuSheetError("飞书 Sheet 中没有可读取的工作表")

        sheet_id = str(sheet.get("sheet_id") or "").strip()
        if not sheet_id:
            raise FeishuSheetError("飞书 Sheet 工作表缺少 sheet_id")
        sheet_name = str(sheet.get("title") or sheet.get("sheet_name") or sheet_id)
        row_count = max(1, int(sheet.get("row_count") or 1))
        col_count = max(1, int(sheet.get("column_count") or 1))
        end_col = _col_name(min(col_count, 52))
        read_range = f"A1:{end_col}{row_count}"

        cell_data = _invoke_read(
            client,
            access_token,
            coords.spreadsheet_token,
            "get_cell_ranges",
            {
                "cell_limit": 1_000_000_000,
                "excel_id": coords.spreadsheet_token,
                "include_styles": False,
                "max_chars": _MAX_CHARS,
                "ranges": [read_range],
                "sheet_id": sheet_id,
            },
        )
        ranges = cell_data.get("ranges") or []
        if not ranges or not isinstance(ranges[0], dict):
            raise FeishuSheetError("飞书 Sheet 中没有可读取的单元格数据")
        result = dict(ranges[0])
        result["spreadsheet_token"] = coords.spreadsheet_token
        result["sheet_id"] = sheet_id
        result["sheet_name"] = sheet_name
        return result
