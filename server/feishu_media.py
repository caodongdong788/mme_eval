"""以用户 ``user_access_token`` 下载飞书云文档/表格图片素材。"""

from __future__ import annotations

from dataclasses import dataclass
import re

import httpx

_BASE = "https://open.feishu.cn/open-apis/drive/v1"
_TIMEOUT = 60.0
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{8,160}$")


class FeishuMediaError(RuntimeError):
    """下载飞书媒体素材失败。"""


@dataclass(frozen=True)
class FeishuMedia:
    content: bytes
    content_type: str


def _client() -> httpx.Client:
    return httpx.Client(timeout=_TIMEOUT, follow_redirects=True)


def fetch_media(access_token: str, token: str) -> FeishuMedia:
    token = (token or "").strip()
    if not _TOKEN_RE.match(token):
        raise FeishuMediaError("非法飞书图片 token")
    if not access_token:
        raise FeishuMediaError("缺少飞书 user_access_token")

    endpoint = f"{_BASE}/medias/{token}/download"
    with _client() as client:
        try:
            resp = client.get(endpoint, headers={"Authorization": f"Bearer {access_token}"})
            content_type = (resp.headers.get("content-type") or "application/octet-stream").split(";")[0]
            if resp.status_code >= 400:
                try:
                    data = resp.json()
                    msg = data.get("msg") or data.get("message") or resp.text[:200]
                    code = data.get("code", resp.status_code)
                except ValueError:
                    msg = resp.text[:200]
                    code = resp.status_code
                raise FeishuMediaError(f"下载飞书图片失败：code={code} msg={msg}")
        except httpx.HTTPError as exc:
            raise FeishuMediaError(f"下载飞书图片失败：{exc}") from exc
    return FeishuMedia(content=resp.content, content_type=content_type)
