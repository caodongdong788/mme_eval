"""Token 用量与成本计算 —— ingest 与 reporter 聚合共用。"""

from __future__ import annotations

from typing import Any

from ..models import CaseResult


def token_cost_from_counts(
    prompt: int, completion: int, pricing: dict[str, Any] | None
) -> float | None:
    """按 prompt/completion 计数与单价配置折算成本；无有效单价时返回 None。"""
    pricing = pricing or {}
    in_price = float(pricing.get("input_per_million", 0.0) or 0.0)
    out_price = float(pricing.get("output_per_million", 0.0) or 0.0)
    if in_price > 0 or out_price > 0:
        return prompt / 1_000_000 * in_price + completion / 1_000_000 * out_price
    return None


def case_token_cost(
    cr: CaseResult, pricing: dict[str, Any] | None
) -> tuple[int | None, float | None]:
    """从一条 CaseResult 算 (总 token, 成本)。仅观测、不否决。

    总 token 优先取 ``per_run_tokens`` 之和，回退到代表性 trace 逐轮求和；无任何 usage
    返回 (None, None)。成本仅在配置非零单价时折算（input/output 分别计价），否则 None。
    """
    usage = getattr(cr.trace, "turn_token_usage", []) if cr.trace else []
    if cr.per_run_tokens:
        total = sum(int(t) for t in cr.per_run_tokens)
    else:
        total = sum(int(u.get("total_tokens", 0)) for u in usage)
    if total == 0 and not usage:
        return None, None
    prompt = sum(int(u.get("prompt_tokens", 0)) for u in usage)
    completion = sum(int(u.get("completion_tokens", 0)) for u in usage)
    return total, token_cost_from_counts(prompt, completion, pricing)
