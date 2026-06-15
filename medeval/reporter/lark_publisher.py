"""把评测报告自动发布到飞书文档。

使用 lark-cli（用户已登录）调用 `docs +create --api-version v2 --doc-format markdown`。
设计要点：
  * 用 subprocess + argv 列表，避免 shell 转义问题
  * 失败时返回 None，并打印 stderr，不抛异常打断主流程
  * 报告太长时（>200KB）先创建骨架，再分段 append（P1 再做）
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess

log = logging.getLogger(__name__)


_MAX_CONTENT_BYTES = 200_000  # lark-cli --content 安全长度估计


def publish_to_lark(
    markdown_content: str,
    parent_folder_token: str = "",
    title_hint: str = "",
) -> str | None:
    """创建一份飞书文档，返回文档 URL。失败返回 None。"""
    if shutil.which("lark-cli") is None:
        log.warning("lark-cli not installed; skipping Feishu publish")
        return None

    content = markdown_content
    # 飞书 docx 会从首个 # 提取标题；若 title_hint 为空则用 markdown 自带的
    if title_hint and not content.lstrip().startswith("#"):
        content = f"# {title_hint}\n\n{content}"

    if len(content.encode("utf-8")) > _MAX_CONTENT_BYTES:
        log.warning(
            "Markdown content is large (%d bytes); truncating for Feishu publish",
            len(content.encode("utf-8")),
        )
        # 截断时尽量保留概览部分
        content = content[: _MAX_CONTENT_BYTES // 2] + "\n\n_（内容过长已截断，完整报告见 HTML/JSON 输出）_"

    cmd = [
        "lark-cli",
        "docs",
        "+create",
        "--api-version",
        "v2",
        "--doc-format",
        "markdown",
        "--content",
        content,
    ]
    if parent_folder_token:
        cmd += ["--parent-token", parent_folder_token]

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )
    except subprocess.TimeoutExpired:
        log.error("lark-cli timed out")
        return None
    except Exception as e:
        log.error("lark-cli invocation failed: %s", e)
        return None

    if proc.returncode != 0:
        log.error(
            "lark-cli docs +create failed (exit %s):\n%s",
            proc.returncode,
            proc.stderr,
        )
        return None

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        log.error("Could not parse lark-cli output as JSON:\n%s", proc.stdout)
        return None

    doc = (data.get("data") or {}).get("document") or {}
    url = doc.get("url") or ""
    if not url:
        log.warning("lark-cli returned no document URL: %s", data)
        return None
    log.info("Feishu doc created: %s", url)
    return url
