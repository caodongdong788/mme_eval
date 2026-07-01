"""以用户 ``user_access_token`` 读取飞书 Base 记录。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

_BASE = "https://open.feishu.cn/open-apis/bitable/v1"
_TIMEOUT = 60.0
_PAGE_SIZE = 500


class FeishuBaseError(RuntimeError):
    """读取飞书 Base 失败。"""


@dataclass(frozen=True)
class BaseCoords:
    app_token: str
    table_id: str
    view_id: str = ""


def _client() -> httpx.Client:
    return httpx.Client(timeout=_TIMEOUT)


def parse_base_url(url: str) -> BaseCoords:
    parsed = urlparse((url or "").strip())
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2 or parts[0] != "base":
        raise FeishuBaseError("飞书 URL 需为 /base/<app_token> 形式")
    app_token = parts[1]
    query = parse_qs(parsed.query)
    table_id = (query.get("table") or [""])[0]
    view_id = (query.get("view") or [""])[0]
    if not app_token or not table_id:
        raise FeishuBaseError("飞书 Base URL 缺少 app_token 或 table 参数")
    return BaseCoords(app_token=app_token, table_id=table_id, view_id=view_id)


def is_base_url(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    parts = [p for p in parsed.path.split("/") if p]
    return bool(parts and parts[0] == "base")


def _check(data: dict[str, Any], what: str) -> dict[str, Any]:
    if data.get("code", 0) != 0:
        raise FeishuBaseError(_format_feishu_error(data, what))
    payload = data.get("data", {})
    return payload if isinstance(payload, dict) else {}


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


def fetch_base_records(access_token: str, url: str) -> list[dict[str, Any]]:
    """读取 URL 指定 Base 表/视图的所有记录。"""
    coords = parse_base_url(url)
    if not access_token:
        raise FeishuBaseError("缺少飞书 user_access_token")

    records: list[dict[str, Any]] = []
    page_token = ""
    endpoint = f"{_BASE}/apps/{coords.app_token}/tables/{coords.table_id}/records/search"
    with _client() as client:
        while True:
            params: dict[str, Any] = {"page_size": _PAGE_SIZE}
            if page_token:
                params["page_token"] = page_token
            body: dict[str, Any] = {}
            if coords.view_id:
                body["view_id"] = coords.view_id
            resp = client.post(
                endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
                json=body,
            )
            try:
                payload = resp.json()
            except httpx.HTTPError as exc:
                raise FeishuBaseError(f"查询飞书 Base 记录失败：{exc}") from exc
            except ValueError as exc:
                raise FeishuBaseError("查询飞书 Base 记录失败：响应不是合法 JSON") from exc
            if resp.status_code >= 400:
                raise FeishuBaseError(_format_feishu_error(payload, "查询飞书 Base 记录"))
            data = _check(payload, "查询飞书 Base 记录")
            items = data.get("items") or []
            records.extend(item for item in items if isinstance(item, dict))
            if not data.get("has_more"):
                break
            page_token = str(data.get("page_token") or "")
            if not page_token:
                break
    return records
