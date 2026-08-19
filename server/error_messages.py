"""面向用户的中文错误说明。

异常原文仍写入服务日志；接口响应只返回用户能理解并能据此处理的中文说明。
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from medeval.evaluation import DIMENSION_LABELS


_FIELD_LABELS = {
    "sample_id": "用例编号",
    "scenario": "场景",
    "level": "难度级别",
    "evaluation": "评测配置",
    "dimension_criteria": "八维评测要求",
    "criteria": "评测要求",
    "reference_answers": "推荐回答",
    "guidelines": "指南扣分点",
    "max_score": "最高扣分",
    "dimension": "关联维度",
}


def _location_label(location: Iterable[Any]) -> str:
    parts = [str(part) for part in location if part not in {"body", "query", "path"}]
    dimension = next((DIMENSION_LABELS[p] for p in parts if p in DIMENSION_LABELS), "")
    field = _FIELD_LABELS.get(parts[-1], parts[-1] if parts else "数据")
    return f"{dimension}的“{field}”" if dimension else field


def _translate_validation_item(item: Mapping[str, Any]) -> str:
    location = list(item.get("loc") or [])
    field = _location_label(location)
    error_type = str(item.get("type") or "")
    context = item.get("ctx") if isinstance(item.get("ctx"), Mapping) else {}
    minimum = context.get("min_length", 1)

    if location and str(location[-1]) == "criteria" and error_type in {
        "too_short",
        "list_too_short",
        "value_error",
    }:
        return (
            f"{field}至少需要保留 {minimum} 条；"
            "如果该维度没有补充要求，请删除整个空维度"
        )
    if error_type == "missing":
        return f"缺少必填项“{field}”"
    if error_type in {"string_type", "string_unicode"}:
        return f"{field}必须填写文本"
    if error_type in {"int_type", "int_parsing"}:
        return f"{field}必须填写整数"
    if error_type in {"list_type"}:
        return f"{field}必须是列表"
    if error_type in {"greater_than_equal", "greater_than"}:
        limit = context.get("ge", context.get("gt", "规定的最小值"))
        return f"{field}不能小于 {limit}"
    if error_type in {"less_than_equal", "less_than"}:
        limit = context.get("le", context.get("lt", "规定的最大值"))
        return f"{field}不能大于 {limit}"

    raw = str(item.get("msg") or "").strip()
    raw = re.sub(r"^Value error,\s*", "", raw, flags=re.IGNORECASE)
    if raw and re.search(r"[\u4e00-\u9fff]", raw):
        return f"{field}：{raw}"
    return f"{field}填写不符合要求，请检查后重试"


def format_validation_errors(
    errors: Iterable[Mapping[str, Any]], *, prefix: str = "数据校验失败"
) -> str:
    """把 Pydantic / FastAPI 的结构化校验错误转为中文。"""

    messages: list[str] = []
    for item in errors:
        message = _translate_validation_item(item)
        if message not in messages:
            messages.append(message)
    return f"{prefix}：{'；'.join(messages)}" if messages else f"{prefix}，请检查填写内容"


def format_validation_exception(exc: Exception, *, prefix: str = "数据校验失败") -> str:
    errors_method = getattr(exc, "errors", None)
    if callable(errors_method):
        try:
            errors = errors_method(include_url=False, include_input=False)
        except TypeError:
            errors = errors_method()
        if isinstance(errors, list):
            return format_validation_errors(errors, prefix=prefix)
    return f"{prefix}，请检查填写内容"


def humanize_error_text(value: Any, *, fallback: str = "操作失败，请稍后重试") -> str:
    """隐藏第三方英文异常，返回适合直接展示的中文说明。"""

    text = str(value or "").strip()
    lowered = text.lower()
    if "expecting value" in lowered or "jsondecode" in lowered or "invalid json" in lowered:
        return "模型没有返回可解析的结果，请稍后重试；如持续出现，请检查模型配置"
    if any(token in lowered for token in ("internalservererror", "internal_server_error", "an internal error has occurred")):
        return "模型服务内部处理失败，请稍后重试；如持续出现，请更换模型或检查模型配置"
    if "badrequesterror" in lowered or "invalid request error" in lowered:
        return "模型服务拒绝了本次请求，请检查模型参数与输入长度后重试"
    if any(token in lowered for token in ("timeout", "timed out", "etimedout")):
        return "请求处理超时，请稍后重试"
    if any(token in lowered for token in ("network error", "failed to fetch", "econnrefused", "connection refused")):
        return "暂时无法连接服务，请检查网络后重试"
    if "bad gateway" in lowered or re.search(r"httpexception:\s*502", lowered):
        return "上游服务暂时不可用，请稍后重试"
    if "service unavailable" in lowered:
        return "服务正在启动或维护中，请稍后重试"
    if re.search(r"[\u4e00-\u9fff]", text):
        return text
    return fallback
