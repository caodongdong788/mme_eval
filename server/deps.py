"""路由共享依赖/工具：消除多个 router 里复制的相同小函数。

放在 ``server`` 顶层而非 ``server/routers`` 内，避免 router 间互相 import 造成的耦合/环依赖。
"""

from __future__ import annotations

from typing import Optional

from .models_db import FeishuUser


def creator_name(current_user: Optional[FeishuUser]) -> Optional[str]:
    """当前登录人显示名（未登录 dev 态返回 None）。"""
    return current_user.name if current_user is not None else None
