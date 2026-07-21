"""Judge 共用的 Case 初始化真值渲染。"""

from __future__ import annotations

import json

from ..models import TestCase


def format_initial_state(case: TestCase) -> str:
    payload = case.initial_state.model_dump(
        mode="json",
        exclude_none=True,
        exclude_defaults=True,
    )
    if not payload:
        return "无"
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
