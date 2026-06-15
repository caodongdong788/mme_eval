"""产物路径安全工具：把任意拼接出的路径限制在受控根目录之内。

所有由外部输入（run 名称 / slug / benchmark 标识）拼接出的 ``outputs/`` / ``uploads/``
路径，落盘读写前都应经 :func:`safe_join` 校验，避免路径穿越（``../``）越界访问。
"""

from __future__ import annotations

from pathlib import Path


def safe_join(root: Path | str, *parts: str) -> Path:
    """在 ``root`` 下安全拼接 ``parts``，越界即抛 ``ValueError``。

    返回 resolve 后的绝对路径，且保证其位于 ``root`` 之内（或等于 ``root``）。
    """
    root_resolved = Path(root).resolve()
    target = (root_resolved / Path(*parts)).resolve()
    if target != root_resolved and not target.is_relative_to(root_resolved):
        raise ValueError(f"路径越界：{target} 不在受控根 {root_resolved} 之内")
    return target
