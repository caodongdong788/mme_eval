"""以用户 ``user_access_token`` 把本地 xlsx 上传并导入为飞书在线表格。

流程（飞书云空间导入，2026-06 核实）：
  1. ``POST /open-apis/drive/v1/medias/upload_all``（parent_type=``ccm_import_open``）→ file_token
  2. ``POST /open-apis/drive/v1/import_tasks``（file_extension=xlsx、type=sheet、point.mount_key=
     目标文件夹 token，空=根目录）→ ticket
  3. 轮询 ``GET /open-apis/drive/v1/import_tasks/{ticket}`` 直到 result.job_status==0 → url

权限：``drive:drive``。失败抛 :class:`FeishuDriveError`（携带可读原因）。

说明：上传/导入接口的字段较多，此实现遵循官方「导入文件概述」的推荐路径；如未来飞书
接口字段调整，仅需改本模块（已与认证、导出端点解耦）。
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

_BASE = "https://open.feishu.cn/open-apis/drive/v1"
_UPLOAD_URL = f"{_BASE}/medias/upload_all"
_IMPORT_URL = f"{_BASE}/import_tasks"
_TIMEOUT = 120.0

# import_task result.job_status：0=成功，1=初始化，2=处理中，其余=错误。
_JOB_SUCCESS = 0
_JOB_PENDING = (1, 2)


class FeishuDriveError(RuntimeError):
    """上传 / 导入飞书云文档失败。"""


def _client() -> httpx.Client:
    """可在测试中 monkeypatch 注入 MockTransport。"""
    return httpx.Client(timeout=_TIMEOUT)


def _check(data: dict, what: str) -> dict:
    if data.get("code", 0) != 0:
        raise FeishuDriveError(
            f"{what} 失败：code={data.get('code')} msg={data.get('msg')}"
        )
    return data.get("data", {})


def _upload(client: httpx.Client, access_token: str, xlsx_path: Path) -> str:
    raw = xlsx_path.read_bytes()
    # 导入场景下 medias/upload_all 必须带 extra（声明目标云文档类型与源扩展名），
    # 否则会被判为 1061004 forbidden。
    resp = client.post(
        _UPLOAD_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        data={
            "file_name": xlsx_path.name,
            "parent_type": "ccm_import_open",
            "size": str(len(raw)),
            "extra": json.dumps({"obj_type": "sheet", "file_extension": "xlsx"}),
        },
        files={"file": (xlsx_path.name, raw)},
    )
    data = _check(resp.json(), "上传文件")
    token = data.get("file_token", "")
    if not token:
        raise FeishuDriveError("上传成功但未返回 file_token")
    return token


def _create_import(
    client: httpx.Client, access_token: str, file_token: str, title: str, folder_token: str
) -> str:
    body = {
        "file_extension": "xlsx",
        "file_token": file_token,
        "type": "sheet",
        "file_name": title,
        "point": {"mount_type": 1, "mount_key": folder_token or ""},
    }
    resp = client.post(
        _IMPORT_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        json=body,
    )
    data = _check(resp.json(), "创建导入任务")
    ticket = data.get("ticket", "")
    if not ticket:
        raise FeishuDriveError("创建导入任务成功但未返回 ticket")
    return ticket


def _poll(
    client: httpx.Client,
    access_token: str,
    ticket: str,
    max_polls: int,
    poll_interval: float,
) -> str:
    for _ in range(max_polls):
        resp = client.get(
            f"{_IMPORT_URL}/{ticket}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        data = _check(resp.json(), "查询导入任务")
        result = data.get("result", {})
        status = result.get("job_status")
        if status == _JOB_SUCCESS:
            url = result.get("url", "")
            if not url:
                raise FeishuDriveError("导入完成但未返回表格 URL")
            return url
        if status in _JOB_PENDING:
            if poll_interval:
                time.sleep(poll_interval)
            continue
        raise FeishuDriveError(
            f"导入任务失败：job_status={status} msg={result.get('job_error_msg')}"
        )
    raise FeishuDriveError("导入任务轮询超时")


def import_xlsx_as_sheet(
    access_token: str,
    xlsx_path: Path,
    *,
    folder_token: str = "",
    title: str = "",
    max_polls: int = 30,
    poll_interval: float = 1.0,
) -> str:
    """上传并导入为在线表格，返回飞书表格 URL。失败抛 FeishuDriveError。"""
    xlsx_path = Path(xlsx_path)
    title = title or xlsx_path.stem
    with _client() as client:
        file_token = _upload(client, access_token, xlsx_path)
        ticket = _create_import(client, access_token, file_token, title, folder_token)
        return _poll(client, access_token, ticket, max_polls, poll_interval)
