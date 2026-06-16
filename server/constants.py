"""平台后端共享常量（分页、对用户可见的错误文案）。"""

from __future__ import annotations

LIST_LIMIT_DEFAULT = 50
LIST_LIMIT_MAX = 100

EVAL_JOB_USER_ERROR = "评测任务执行失败，详见服务端日志"
PAIRWISE_JOB_USER_ERROR = "Pairwise 对比执行失败，详见服务端日志"
