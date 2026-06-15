"""medeval 评测平台后端服务（FastAPI）。

在 medeval 命令行框架之上叠加：评测结果与 benchmark 的持久化、benchmark 库管理、
评测任务调度（JobRunner）与 REST API。判分核心（medeval/judges、models、reporter）零改动，
本包仅复用 ``medeval.service.evaluate`` 等编排函数。

参见 OpenSpec change ``add-eval-platform``。
"""

from __future__ import annotations

__all__ = ["create_app"]


def create_app():
    """惰性导入构造 FastAPI app（避免在未装 server 依赖时 import 顶层即失败）。"""
    from .app import create_app as _create_app

    return _create_app()
