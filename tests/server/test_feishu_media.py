"""飞书媒体素材下载客户端（mock httpx，不打真实网络）。"""

from __future__ import annotations

import httpx
import pytest

from server import feishu_media as fm


def test_fetch_media_downloads_bytes(monkeypatch):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.headers["Authorization"] == "Bearer u-token"
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=b"jpg")

    monkeypatch.setattr(
        fm, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )

    media = fm.fetch_media("u-token", "Rhb9bkUUfoA7rSxq4YzcVTT8nAs")

    assert media.content == b"jpg"
    assert media.content_type == "image/jpeg"
    assert seen[0].url.path == "/open-apis/drive/v1/medias/Rhb9bkUUfoA7rSxq4YzcVTT8nAs/download"


def test_fetch_media_rejects_invalid_token():
    with pytest.raises(fm.FeishuMediaError, match="非法"):
        fm.fetch_media("u-token", "../bad")


def test_fetch_media_wraps_feishu_error(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"code": 99991679, "msg": "denied"})

    monkeypatch.setattr(
        fm, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(fm.FeishuMediaError, match="denied"):
        fm.fetch_media("u-token", "Rhb9bkUUfoA7rSxq4YzcVTT8nAs")
