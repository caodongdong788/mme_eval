"""八维与指南 verdict 中文标签。"""

from __future__ import annotations

from .evaluation import DIMENSION_LABELS, EvaluationDimension

FINGERPRINT_LABELS = {
    "dimension": "八维评分",
    "guideline": "指南覆盖评分",
}


def judge_verdict_label(name: str | None) -> str:
    if not name:
        return "-"
    if name == "dimension":
        return "八维评分"
    if name == "guideline":
        return "指南评分"
    if name.startswith("dimension."):
        key = name.removeprefix("dimension.")
        try:
            return DIMENSION_LABELS[EvaluationDimension(key)]
        except ValueError:
            return name
    if name.startswith("guideline."):
        return f"指南·{name.removeprefix('guideline.')}"
    return name


def judge_verdict_label_map() -> dict[str, str]:
    return {
        "dimension": "八维评分",
        "guideline": "指南评分",
        **{
            f"dimension.{dimension.value}": DIMENSION_LABELS[dimension]
            for dimension in EvaluationDimension
        },
    }
