"""八维度 + 指南缺分扣减的报告层评分入口。

单题固定三端各15分，总分45分；医学安全性为0时总分归零。
本模块不读取权重、score profile 或历史四模块配置。
"""

from __future__ import annotations

from typing import Any

from ..evaluation import EvaluationDimension
from ..models import CaseResult
from .eight_dimension_scoring import score_eight_dimension_case

GRADE_EXCELLENT = "优秀"
GRADE_GOOD = "良好"
GRADE_PASS = "合格"
GRADE_FAIL = "不合格"


def score_case(result: CaseResult) -> dict[str, Any]:
    """对单条 Case 计算八维原始分、指南扣分、三端分和45分总分。"""
    return score_eight_dimension_case(result)


def apply_grading(results: list[CaseResult]) -> None:
    """将最终评分就地写入 CaseResult。"""
    for result in results:
        breakdown = score_case(result)
        result.dimension_raw_scores = breakdown["raw_dimensions"]
        result.guideline_scores = breakdown["guideline_scores"]
        result.dimension_scores = breakdown["dimensions"]
        result.dimension_max = breakdown["dimension_max"]
        result.end_scores = breakdown["ends"]
        result.composite_score = breakdown["total"]
        result.grade = breakdown["grade"]
        result.score_deductions = breakdown["deductions"]
        result.medical_safety_passed = (
            breakdown["raw_dimensions"].get(EvaluationDimension.medical_safety.value)
            == 5.0
        )
        result.release_passed = result.trace.error is None and bool(breakdown["passed"])


def grading_summary(results: list[CaseResult]) -> dict[str, Any]:
    """聚合评级分布、平均总分、三端与八维平均分。"""
    distribution = {
        GRADE_EXCELLENT: 0,
        GRADE_GOOD: 0,
        GRADE_PASS: 0,
        GRADE_FAIL: 0,
    }
    totals: list[float] = []
    dimension_values = {dimension.value: [] for dimension in EvaluationDimension}
    end_values = {role: [] for role in ("doctor", "nurse", "user")}

    for result in results:
        if result.grade in distribution:
            distribution[result.grade] += 1
        if result.composite_score is not None:
            totals.append(float(result.composite_score))
        for dimension, values in dimension_values.items():
            if dimension in result.dimension_scores:
                values.append(float(result.dimension_scores[dimension]))
        for role, values in end_values.items():
            if role in result.end_scores:
                values.append(float(result.end_scores[role]))

    if not totals and not any(dimension_values.values()):
        return {}

    def averages(groups: dict[str, list[float]]) -> dict[str, float | None]:
        return {
            key: (sum(values) / len(values) if values else None)
            for key, values in groups.items()
        }

    return {
        "avg_composite": sum(totals) / len(totals) if totals else None,
        "distribution": distribution,
        "avg_dimension": averages(dimension_values),
        "avg_end": averages(end_values),
    }
