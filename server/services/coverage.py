"""Benchmark 覆盖度统计：只读 Case schema，不把推断结果写回 Case。"""

from __future__ import annotations

from collections import Counter
from typing import Any

from medeval.models import TestCase


def benchmark_coverage(cases: list[TestCase]) -> dict[str, Any]:
    total = len(cases)

    def counts(values: list[str]) -> dict[str, int]:
        return dict(sorted(Counter(value or "未填写" for value in values).items()))

    dimensions: Counter[str] = Counter()
    assertion_types: Counter[str] = Counter()
    mechanisms: Counter[str] = Counter()
    for case in cases:
        dimensions.update(dimension.value for dimension in case.evaluation.dimension_criteria)
        assertion_types.update(assertion.type for assertion in case.evaluation.assertions)
        if case.evaluation.guidelines:
            mechanisms["指南"] += 1
        if case.evaluation.assertions:
            mechanisms["可验证断言"] += 1
        if not case.initial_state.is_empty():
            mechanisms["用户画像/长期记忆"] += 1
        if case.conversation is not None:
            mechanisms["目标驱动多轮"] += 1
        if len([turn for turn in case.turns if turn.role == "user"]) > 1:
            mechanisms["固定多轮"] += 1
    return {
        "total": total,
        "by_level": counts([case.level.value for case in cases]),
        "by_scenario": counts([case.scenario for case in cases]),
        "by_source": counts([case.source.value for case in cases]),
        "by_case_type": counts([case.case_type for case in cases]),
        "dimensions": dict(sorted(dimensions.items())),
        "assertion_types": dict(sorted(assertion_types.items())),
        "mechanisms": dict(sorted(mechanisms.items())),
        "coverage_rate": {
            "with_guidelines": sum(bool(case.evaluation.guidelines) for case in cases) / total if total else 0,
            "with_assertions": sum(bool(case.evaluation.assertions) for case in cases) / total if total else 0,
            "with_memory": sum(not case.initial_state.is_empty() for case in cases) / total if total else 0,
            "multi_turn": sum(case.conversation is not None or len([turn for turn in case.turns if turn.role == "user"]) > 1 for case in cases) / total if total else 0,
        },
    }
