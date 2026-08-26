"""版本测试报告使用的评测周期汇总。

接口返回结构化图表数据，不返回页面截图。调用方可在网页、飞书文档等不同
载体中用同一数据重绘，避免截图裁切、分辨率和样式漂移。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from medeval.evaluation import DIMENSION_LABELS, EvaluationDimension

from ..models_db import EvalRun
from .attribution_summary import attribution_category_stats, cx_agent_optimization_counts


_SHANGHAI = ZoneInfo("Asia/Shanghai")


def _date_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    def to_utc_naive(day: date) -> datetime:
        return (
            datetime.combine(day, time.min, tzinfo=_SHANGHAI)
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )

    return to_utc_naive(start_date), to_utc_naive(end_date + timedelta(days=1))


def _shanghai_date(value: datetime) -> date:
    instant = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return instant.astimezone(_SHANGHAI).date()


def _runs(
    session: Session,
    start_date: date,
    end_date: date,
    trigger_type: str,
) -> list[EvalRun]:
    start_at, end_at = _date_bounds(start_date, end_date)
    return list(
        session.scalars(
            select(EvalRun)
            .options(selectinload(EvalRun.benchmark))
            .where(
                EvalRun.created_at >= start_at,
                EvalRun.created_at < end_at,
                EvalRun.trigger_type == trigger_type,
            )
            .order_by(EvalRun.created_at.asc(), EvalRun.id.asc())
        )
    )


def _completed(runs: list[EvalRun]) -> list[EvalRun]:
    return [run for run in runs if run.status == "success"]


def _summary(runs: list[EvalRun]) -> dict[str, Any]:
    completed = _completed(runs)
    total_cases = sum(max(int(run.total or 0), 0) for run in completed)
    passed_cases = sum(min(max(int(run.passed or 0), 0), max(int(run.total or 0), 0)) for run in completed)
    scores = [
        (float(value), max(int(run.total or 0), 1))
        for run in completed
        if isinstance((value := (run.grading or {}).get("avg_composite")), (int, float))
        and not isinstance(value, bool)
    ]
    score_weight = sum(weight for _value, weight in scores)
    return {
        "evaluation_count": len(runs),
        "completed_count": len(completed),
        "running_count": sum(run.status in {"pending", "running"} for run in runs),
        "failed_count": sum(run.status == "failed" for run in runs),
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": max(total_cases - passed_cases, 0),
        "average_pass_rate": round(passed_cases / total_cases * 100, 1) if total_cases else None,
        "medical_safety_failed": sum(max(int(run.medical_safety_failed or 0), 0) for run in completed),
        "average_score": (
            round(sum(value * weight for value, weight in scores) / score_weight, 1) if score_weight else None
        ),
    }


def _latest_by_day_and_benchmark(runs: list[EvalRun]) -> dict[date, dict[str, EvalRun]]:
    selected: dict[date, dict[str, EvalRun]] = defaultdict(dict)
    for run in _completed(runs):
        day = _shanghai_date(run.created_at)
        benchmark_key = str(run.benchmark_id) if run.benchmark_id is not None else f"unassigned:{run.id}"
        current = selected[day].get(benchmark_key)
        if current is None or (run.created_at, run.id) > (current.created_at, current.id):
            selected[day][benchmark_key] = run
    return selected


def _pass_rate_trend(runs: list[EvalRun]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for day, by_benchmark in sorted(_latest_by_day_and_benchmark(runs).items()):
        total = sum(max(int(run.total or 0), 0) for run in by_benchmark.values())
        if total <= 0:
            continue
        passed = sum(min(max(int(run.passed or 0), 0), max(int(run.total or 0), 0)) for run in by_benchmark.values())
        output.append(
            {
                "date": day.isoformat(),
                "pass_rate": round(passed / total * 100, 1),
                "passed_cases": passed,
                "total_cases": total,
            }
        )
    return output


def _attribution_trend(runs: list[EvalRun]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for day, by_benchmark in sorted(_latest_by_day_and_benchmark(runs).items()):
        counts = [cx_agent_optimization_counts(run.attribution_summary) for run in by_benchmark.values()]
        available = [value for value in counts if value is not None]
        if not available:
            continue
        output.append(
            {
                "date": day.isoformat(),
                "optimization_count": sum(value[0] for value in available),
                "p0_count": sum(value[1] for value in available),
            }
        )
    return output


def _benchmark_results(runs: list[EvalRun]) -> list[dict[str, Any]]:
    grouped: dict[str, list[EvalRun]] = defaultdict(list)
    for run in _completed(runs):
        name = run.benchmark.name if run.benchmark is not None else "未关联 Benchmark"
        grouped[name].append(run)
    output: list[dict[str, Any]] = []
    for name, values in grouped.items():
        total = sum(max(int(run.total or 0), 0) for run in values)
        passed = sum(min(max(int(run.passed or 0), 0), max(int(run.total or 0), 0)) for run in values)
        output.append(
            {
                "name": name,
                "evaluation_count": len(values),
                "total_cases": total,
                "passed_cases": passed,
                "failed_cases": max(total - passed, 0),
                "pass_rate": round(passed / total * 100, 1) if total else None,
            }
        )
    return sorted(output, key=lambda row: (-row["evaluation_count"], row["name"]))


def _evaluation_problems(runs: list[EvalRun]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    case_types: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "passed": 0})
    dimension_sums = {dimension.value: 0.0 for dimension in EvaluationDimension}
    dimension_weights = {dimension.value: 0 for dimension in EvaluationDimension}
    for run in _completed(runs):
        weight = max(int(run.total or 0), 1)
        dimensions = (run.grading or {}).get("avg_dimension") or {}
        if isinstance(dimensions, dict):
            for dimension in EvaluationDimension:
                value = dimensions.get(dimension.value)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    dimension_sums[dimension.value] += float(value) * weight
                    dimension_weights[dimension.value] += weight
        for name, raw in (run.by_case_type or {}).items():
            if not isinstance(raw, dict):
                continue
            total = raw.get("total")
            passed = raw.get("passed")
            if not isinstance(total, (int, float)) or not isinstance(passed, (int, float)):
                continue
            total_int = max(int(total), 0)
            if total_int == 0:
                continue
            case_types[str(name).strip() or "未分类"]["total"] += total_int
            case_types[str(name).strip() or "未分类"]["passed"] += min(max(int(passed), 0), total_int)
    problems = [
        {
            "label": name,
            "total_cases": values["total"],
            "failed_cases": values["total"] - values["passed"],
            "failure_rate": round((values["total"] - values["passed"]) / values["total"] * 100, 1),
        }
        for name, values in case_types.items()
    ]
    problems.sort(key=lambda row: (-row["failure_rate"], -row["failed_cases"], row["label"]))
    dimensions = [
        {
            "key": dimension.value,
            "label": DIMENSION_LABELS[dimension],
            "average": (
                round(dimension_sums[dimension.value] / dimension_weights[dimension.value], 2)
                if dimension_weights[dimension.value]
                else None
            ),
        }
        for dimension in EvaluationDimension
        if dimension_weights[dimension.value]
    ]
    dimensions.sort(key=lambda row: (row["average"], row["label"]))
    return problems, dimensions


def _attribution_problems(runs: list[EvalRun]) -> dict[str, Any]:
    latest: dict[str, EvalRun] = {}
    for run in _completed(runs):
        if cx_agent_optimization_counts(run.attribution_summary) is None:
            continue
        key = str(run.benchmark_id) if run.benchmark_id is not None else f"unassigned:{run.id}"
        current = latest.get(key)
        if current is None or (run.created_at, run.id) > (current.created_at, current.id):
            latest[key] = run
    first: dict[str, int] = defaultdict(int)
    second: dict[tuple[str, str], int] = defaultdict(int)
    attributed_cases = 0
    for run in latest.values():
        stats = attribution_category_stats(run.attribution_summary)
        attributed_cases += int(stats["attributed_case_count"])
        for row in stats["first_level"]:
            first[str(row["label"])] += int(row["case_count"])
        for row in stats["second_level"]:
            second[(str(row.get("parent_label") or "未分类"), str(row["label"]))] += int(row["case_count"])
    first_level = [
        {"label": label, "case_count": count}
        for label, count in sorted(first.items(), key=lambda item: (-item[1], item[0]))
    ]
    second_level = [
        {"parent_label": parent, "label": label, "case_count": count}
        for (parent, label), count in sorted(second.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
    ]
    return {
        "attributed_case_count": attributed_cases,
        "first_level": first_level,
        "second_level": second_level,
    }


def version_report_summary(
    session: Session,
    *,
    start_date: date,
    end_date: date,
    trigger_type: str,
    dashboard_url: str,
) -> dict[str, Any]:
    runs = _runs(session, start_date, end_date, trigger_type)
    duration = (end_date - start_date).days + 1
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=duration - 1)
    previous_runs = _runs(session, previous_start, previous_end, trigger_type)
    evaluation_problems, dimension_scores = _evaluation_problems(runs)
    return {
        "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        "dashboard_url": dashboard_url,
        "summary": _summary(runs),
        "previous_summary": _summary(previous_runs),
        "pass_rate_trend": _pass_rate_trend(runs),
        "attribution_trend": _attribution_trend(runs),
        "benchmark_results": _benchmark_results(runs),
        "evaluation_problems": evaluation_problems,
        "dimension_scores": dimension_scores,
        "attribution_problems": _attribution_problems(runs),
    }
