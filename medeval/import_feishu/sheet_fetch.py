"""通过 lark-cli 拉取飞书电子表格。"""

from __future__ import annotations

import json
import subprocess
from typing import Any


class LarkCliError(RuntimeError):
    pass


def _run_lark_cli(args: list[str]) -> dict[str, Any]:
    cmd = ["lark-cli", *args]
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise LarkCliError(
            "未找到 lark-cli。请先安装并执行: lark-cli auth login"
        ) from exc
    if proc.returncode != 0:
        stderr = (proc.stderr or proc.stdout or "").strip()
        raise LarkCliError(f"lark-cli 失败 ({proc.returncode}): {stderr}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise LarkCliError(f"lark-cli 输出非 JSON: {proc.stdout[:200]}") from exc


def resolve_sheet_id(url: str, worksheet: str | None = None) -> str:
    """从 +info 解析 sheet_id；worksheet 为工作表标题时按标题匹配。"""
    data = _run_lark_cli(["sheets", "+info", "--url", url])
    sheets = data.get("sheets") or data.get("data", {}).get("sheets") or []
    if not sheets:
        raise LarkCliError("表格无工作表或 +info 返回为空")
    if worksheet:
        for sh in sheets:
            title = sh.get("title") or sh.get("name") or ""
            if title == worksheet:
                return sh["sheet_id"]
        raise LarkCliError(f"未找到工作表: {worksheet}")
    return sheets[0]["sheet_id"]


def fetch_sheet_grid(
    url: str,
    *,
    worksheet: str | None = None,
    sheet_id: str | None = None,
    max_rows: int = 500,
) -> list[list[str]]:
    """读取整张表（含表头），返回字符串二维数组。"""
    sid = sheet_id or resolve_sheet_id(url, worksheet)
    range_spec = f"{sid}!A1:ZZ{max_rows}"
    data = _run_lark_cli(
        [
            "sheets",
            "+read",
            "--url",
            url,
            "--range",
            range_spec,
            "--value-render-option",
            "ToString",
        ]
    )
    values = data.get("values")
    if values is None:
        values = data.get("data", {}).get("valueRange", {}).get("values")
    if not values:
        raise LarkCliError("表格读取结果为空")
    # 统一为 str 单元格
    return [[str(c) if c is not None else "" for c in row] for row in values]
