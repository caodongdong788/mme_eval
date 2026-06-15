"""统计辅助：bootstrap 置信区间（纯标准库、确定性可复现）。

参见 OpenSpec change ``enhance-eval-engine``（借鉴 AgentScope Studio 把"通过率"呈现为
带置信区间的统计分布，避免小样本/N-runs 下的误导性单点值）。

设计要点：
  * 仅依赖标准库 ``random``，给定 ``seed`` 时结果逐字节可复现（保证 report.json 稳定、可 diff）。
  * 输入为布尔样本（每条用例 pass/fail），统计量为均值（= 通过率）。
  * 空样本返回空 dict，调用方据此跳过渲染；不抛错。
  * 纯度量：绝不参与任何判分、否决或 ``release_passed`` 口径。
"""

from __future__ import annotations

import random
from typing import Sequence


def _quantile(sorted_vals: list[float], q: float) -> float:
    """线性插值分位数（输入须已排序）。"""
    if not sorted_vals:
        return 0.0
    if q <= 0:
        return sorted_vals[0]
    if q >= 1:
        return sorted_vals[-1]
    idx = q * (len(sorted_vals) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def bootstrap_ci(
    samples: Sequence[bool],
    n_resamples: int = 1000,
    confidence: float = 0.95,
    seed: int | None = 0,
) -> dict:
    """对布尔样本（pass/fail）的通过率做 bootstrap 置信区间。

    返回 ``{"point", "low", "high", "confidence", "n"}``；空样本返回 ``{}``。
    ``n_resamples<=0`` 时退化为点估计（low=high=point）。
    """
    n = len(samples)
    if n == 0:
        return {}
    data = [1.0 if s else 0.0 for s in samples]
    point = sum(data) / n
    if n_resamples <= 0:
        return {
            "point": point,
            "low": point,
            "high": point,
            "confidence": confidence,
            "n": n,
        }
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_resamples):
        total = 0.0
        for _ in range(n):
            total += data[rng.randrange(n)]
        means.append(total / n)
    means.sort()
    alpha = (1.0 - confidence) / 2.0
    return {
        "point": point,
        "low": _quantile(means, alpha),
        "high": _quantile(means, 1.0 - alpha),
        "confidence": confidence,
        "n": n,
    }
