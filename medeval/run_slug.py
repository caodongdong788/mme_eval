"""评测 run 目录名 / ``RunReport.run_name`` 生成。

``config.yaml`` 的 ``run.name`` 只写模型 + 用例集标识（如 ``doubao_breast_cancer``）；
每次 ``medeval run`` 自动追加**当天日期**与毫秒时间戳，避免手改日期且保证目录唯一。
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime

# 路径危险字符：分隔符与控制字符（用作目录名前必须剔除，防止路径穿越）。
_UNSAFE_CHARS = re.compile(r"[\\/\x00-\x1f]+")
# Linux 等常见文件系统的单个目录名上限为 255 bytes。为预留运行产物目录的
# 跨平台兼容空间，run slug 自身采用更保守的上限；注意中文需要按 UTF-8 字节数计算。
MAX_RUN_SLUG_BYTES = 180


def _sanitize_label(run_label: str) -> str:
    """消毒 run 名用作目录名：去路径分隔符 / 控制字符 / ``..`` 穿越片段。

    仅剔除危险字符，保留中文、字母、数字、``._-``，不改变合法标签的产出。
    """
    label = (run_label or "default").strip()
    label = _UNSAFE_CHARS.sub("_", label)
    while ".." in label:
        label = label.replace("..", "_")
    label = label.strip(". ")
    return label or "default"


def _truncate_utf8(value: str, max_bytes: int) -> str:
    """在不截断 UTF-8 字符的前提下，把字符串限制在给定字节数内。"""
    if len(value.encode("utf-8")) <= max_bytes:
        return value
    kept: list[str] = []
    used = 0
    for char in value:
        size = len(char.encode("utf-8"))
        if used + size > max_bytes:
            break
        kept.append(char)
        used += size
    return "".join(kept)


def make_run_slug(run_label: str, *, now: datetime | None = None) -> str:
    """生成唯一 run 标识，用作 ``outputs/<slug>/`` 与 ``RunReport.run_name``。

    常规格式：``{run_label}_{YYYY-MM-DD}_{unix_ms}``（日期取 ``now`` 的本地日历日）。
    ``run_label`` 会先经路径消毒，确保 slug 不含分隔符 / ``..``。当名称过长时，
    保留可读前缀并附加原始名称哈希，保证目录名不超过文件系统安全字节上限。
    """
    label = _sanitize_label(run_label)
    t = now or datetime.now()
    day = t.strftime("%Y-%m-%d")
    ms = int(t.timestamp() * 1000)
    suffix = f"_{day}_{ms}"
    candidate = f"{label}{suffix}"
    if len(candidate.encode("utf-8")) <= MAX_RUN_SLUG_BYTES:
        return candidate

    label_hash = hashlib.sha256(label.encode("utf-8")).hexdigest()[:12]
    truncation_suffix = f"_{label_hash}{suffix}"
    prefix_bytes = MAX_RUN_SLUG_BYTES - len(truncation_suffix.encode("utf-8"))
    return f"{_truncate_utf8(label, prefix_bytes)}{truncation_suffix}"
