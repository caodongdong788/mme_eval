"""runs 路由包：发起评测 / 列表 / 重判 / 用例 / 人审 / diff。

子模块在 import 时向共享 ``router`` 注册端点。以下 re-export 供测试
``monkeypatch.setattr("server.routers.runs.*")`` 与路由处理器解析。
"""

from medeval.reporter.lark_sheet_publisher import publish_xlsx_to_lark

from ...eval_job import (
    build_eval_job,
    build_rejudge_job,
    build_resume_job,
    preview_rejudge_case,
)
from ...feishu_drive import import_xlsx_as_sheet
from ._router import router

from . import cases as _cases  # noqa: F401
from . import crud as _crud  # noqa: F401
from . import rejudge as _rejudge  # noqa: F401
from . import review as _review  # noqa: F401

__all__ = [
    "router",
    "build_eval_job",
    "build_rejudge_job",
    "build_resume_job",
    "preview_rejudge_case",
    "publish_xlsx_to_lark",
    "import_xlsx_as_sheet",
]
