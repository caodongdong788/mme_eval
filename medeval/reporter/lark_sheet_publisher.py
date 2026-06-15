"""把 transcripts.xlsx 上传为飞书 Sheet 文档。

参见 OpenSpec change ``add-transcript-excel-output``。

实现策略：
  1. 优先用 ``lark-cli drive +import``（lark-cli >=最新版支持把本地 xlsx 上传为飞书在线表格）
  2. 若 lark-cli 不存在或子命令失败 → 返回 None + warning，主流程不阻断

错误处理与 ``lark_publisher.publish_to_lark`` 对齐：永不抛异常打断主流程。
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def _try_import_via_drive(
    xlsx_path: Path,
    parent_folder_token: str,
    title: str,
) -> str | None:
    """尝试 ``lark-cli drive +import``。

    lark-cli 的 drive 子命令在新近版本中支持把本地文件导入为飞书在线文档/表格
    （docx / sheet / bitable）。我们传 ``--type sheet`` 让 xlsx 落成在线表格。
    若该子命令不存在、缺 scope 或参数不兼容，调用者会拿到 None。

    Lark-cli 1.0.32+ 实际 flag（参见 ``lark-cli drive +import --help``）：
      --file <path>           本地文件 —— **必须为 cwd 下的相对路径**，传绝对路径会被
                              ``unsafe file path`` 拒绝。我们用文件父目录作为 cwd，
                              只把 basename 传给 lark-cli，绕过该限制。
      --type <docx|sheet|bitable>
      --name <title>          导入后的文件名（不带扩展名）
      --folder-token <token>  目标文件夹 token，省略则落根目录
    """
    cmd = [
        "lark-cli",
        "drive",
        "+import",
        "--file",
        xlsx_path.name,
        "--type",
        "sheet",
    ]
    if title:
        cmd += ["--name", title]
    if parent_folder_token:
        cmd += ["--folder-token", parent_folder_token]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(xlsx_path.parent),
        )
    except subprocess.TimeoutExpired:
        log.error("lark-cli drive +import timed out")
        return None
    except Exception as e:
        log.error("lark-cli drive +import invocation failed: %s", e)
        return None

    if proc.returncode != 0:
        log.warning(
            "lark-cli drive +import failed (exit %s):\n%s",
            proc.returncode,
            proc.stderr,
        )
        return None

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        log.warning(
            "Could not parse lark-cli drive +import output as JSON:\n%s", proc.stdout
        )
        return None

    # lark-cli 的 drive 返回结构通常是 {"data": {"file": {"url": "..."}}} 或类似嵌套
    for path_keys in (
        ("data", "file", "url"),
        ("data", "url"),
        ("data", "document", "url"),
        ("file", "url"),
    ):
        cur = data
        for k in path_keys:
            if not isinstance(cur, dict):
                cur = None
                break
            cur = cur.get(k)
        if isinstance(cur, str) and cur:
            log.info("Feishu sheet imported: %s", cur)
            return cur

    log.warning("lark-cli drive +import returned no URL: %s", data)
    return None


def publish_xlsx_to_lark(
    xlsx_path: Path,
    parent_folder_token: str = "",
    title: str = "",
) -> str | None:
    """把本地 xlsx 上传为飞书 Sheet 文档；失败返回 None（不抛异常）。"""
    if not xlsx_path.exists():
        log.error("transcripts xlsx not found: %s", xlsx_path)
        return None
    if shutil.which("lark-cli") is None:
        log.warning("lark-cli not installed; skipping Feishu sheet publish")
        return None
    return _try_import_via_drive(xlsx_path, parent_folder_token, title)
