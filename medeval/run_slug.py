"""评测 run 目录名 / ``RunReport.run_name`` 生成。

``config.yaml`` 的 ``run.name`` 只写模型 + 用例集标识（如 ``doubao_breast_cancer``）；
每次 ``medeval run`` 自动追加**当天日期**与毫秒时间戳，避免手改日期且保证目录唯一。
"""

from __future__ import annotations

import re
from datetime import datetime

# 路径危险字符：分隔符与控制字符（用作目录名前必须剔除，防止路径穿越）。
_UNSAFE_CHARS = re.compile(r"[\\/\x00-\x1f]+")


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


def make_run_slug(run_label: str, *, now: datetime | None = None) -> str:
    """生成唯一 run 标识，用作 ``outputs/<slug>/`` 与 ``RunReport.run_name``。

    格式：``{run_label}_{YYYY-MM-DD}_{unix_ms}``（日期取 ``now`` 的本地日历日）。
    ``run_label`` 会先经路径消毒，确保 slug 不含分隔符 / ``..``。
    """
    label = _sanitize_label(run_label)
    t = now or datetime.now()
    day = t.strftime("%Y-%m-%d")
    ms = int(t.timestamp() * 1000)
    return f"{label}_{day}_{ms}"
