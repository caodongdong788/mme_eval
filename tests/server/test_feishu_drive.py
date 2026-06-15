"""以用户 token 上传 xlsx 并导入为飞书在线表格（mock httpx）。"""

from __future__ import annotations

import json

import httpx
import pytest

from server import feishu_drive as fd


def _write_xlsx(tmp_path):
    p = tmp_path / "report_transcripts.xlsx"
    p.write_bytes(b"PK\x03\x04 fake xlsx bytes")
    return p


def test_import_xlsx_happy_path(tmp_path, monkeypatch):
    xlsx = _write_xlsx(tmp_path)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        seen.append((request.method, path))
        if path.endswith("/medias/upload_all"):
            # 必须带 extra（声明导入目标类型与源扩展名）
            assert b'ccm_import_open' in request.content
            assert b'"obj_type": "sheet"' in request.content
            assert b'"file_extension": "xlsx"' in request.content
            return httpx.Response(200, json={"code": 0, "data": {"file_token": "ftok"}})
        if path.endswith("/import_tasks") and request.method == "POST":
            body = json.loads(request.content.decode())
            assert body["file_extension"] == "xlsx"
            assert body["file_token"] == "ftok"
            assert body["type"] == "sheet"
            assert body["point"]["mount_type"] == 1
            assert body["point"]["mount_key"] == "fld_target"
            return httpx.Response(200, json={"code": 0, "data": {"ticket": "tk1"}})
        if "/import_tasks/tk1" in path:
            # 第一次处理中，第二次成功
            n = sum(1 for m, p in seen if "/import_tasks/tk1" in p)
            if n == 1:
                return httpx.Response(
                    200, json={"code": 0, "data": {"result": {"job_status": 2}}}
                )
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "result": {
                            "job_status": 0,
                            "token": "shtok",
                            "url": "https://feishu.cn/sheets/shtok",
                            "type": "sheet",
                        }
                    },
                },
            )
        return httpx.Response(404, json={"code": 1, "msg": "unexpected"})

    monkeypatch.setattr(
        fd, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    url = fd.import_xlsx_as_sheet(
        "u-acc", xlsx, folder_token="fld_target", title="我的报告", poll_interval=0
    )
    assert url == "https://feishu.cn/sheets/shtok"
    # 上传 → 创建导入 → 轮询(2次)
    assert ("POST", "/open-apis/drive/v1/medias/upload_all") in seen
    assert ("POST", "/open-apis/drive/v1/import_tasks") in seen


def test_import_xlsx_empty_folder_means_root(tmp_path, monkeypatch):
    xlsx = _write_xlsx(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/medias/upload_all"):
            return httpx.Response(200, json={"code": 0, "data": {"file_token": "ftok"}})
        if path.endswith("/import_tasks") and request.method == "POST":
            body = json.loads(request.content.decode())
            assert body["point"]["mount_key"] == ""  # 空=根目录
            return httpx.Response(200, json={"code": 0, "data": {"ticket": "tk1"}})
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"result": {"job_status": 0, "url": "https://feishu.cn/x"}},
            },
        )

    monkeypatch.setattr(
        fd, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    url = fd.import_xlsx_as_sheet("u-acc", xlsx, folder_token="", poll_interval=0)
    assert url == "https://feishu.cn/x"


def test_import_xlsx_upload_error_raises(tmp_path, monkeypatch):
    xlsx = _write_xlsx(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 1061073, "msg": "no scope auth"})

    monkeypatch.setattr(
        fd, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(fd.FeishuDriveError):
        fd.import_xlsx_as_sheet("u-acc", xlsx, poll_interval=0)


def test_import_xlsx_job_error_raises(tmp_path, monkeypatch):
    xlsx = _write_xlsx(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/medias/upload_all"):
            return httpx.Response(200, json={"code": 0, "data": {"file_token": "ftok"}})
        if path.endswith("/import_tasks") and request.method == "POST":
            return httpx.Response(200, json={"code": 0, "data": {"ticket": "tk1"}})
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"result": {"job_status": 3, "job_error_msg": "boom"}},
            },
        )

    monkeypatch.setattr(
        fd, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(fd.FeishuDriveError):
        fd.import_xlsx_as_sheet("u-acc", xlsx, poll_interval=0)
