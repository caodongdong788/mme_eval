"""面向 Open API 的归因任务只读投影。

归因原始结果还包含评测判据/判分工具的复核信息；该投影只暴露已经确认的
cx-agent 优化项，避免调用方把评测侧待复核信息误当作 Agent 缺陷处理。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from urllib.parse import quote

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from medeval.evaluation import DIMENSION_LABELS, EvaluationDimension

from ..models_db import AttributionTask, AttributionTaskItem, CaseResultRow, EvalRun
from .attribution_issue_categories import classify_evaluation_issue
from .attribution_summary import build_task_diagnostic_summary, recommendation_category
from .attribution_taxonomy import (
    current_optimization_category,
    normalize_optimization_classification,
)
from .case_evaluation_markdown import build_case_evaluation_markdown


_DIMENSION_ORDER = [dimension.value for dimension in EvaluationDimension]
_DIMENSION_LABELS = {
    dimension.value: label for dimension, label in DIMENSION_LABELS.items()
}
_PRIORITY_ORDER = ("P0", "P1", "P2")
_PRIORITY_LABELS = {
    "P0": "最高优先级",
    "P1": "较高优先级",
    "P2": "一般优先级",
}


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _analysis(value: Any) -> dict[str, Any]:
    return _record(_record(value).get("analysis"))


def _agent_recommendations(values: Any) -> list[dict[str, Any]]:
    return [
        {**value, "scope": "cx_agent"}
        for value in values or []
        if isinstance(value, dict) and recommendation_category(value) == "cx_agent_issue"
    ]


def _agent_deductions(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """保留 CX-Agent 已确认项，以及需要补齐 RAG 可回链证据的项。"""
    output: list[dict[str, Any]] = []
    for deduction in analysis.get("deduction_analyses") or []:
        if not isinstance(deduction, dict):
            continue
        evaluation_issue_category = classify_evaluation_issue(deduction)
        if (
            deduction.get("deduction_validation") != "supported"
            and evaluation_issue_category != "missing_rag_reference"
        ):
            continue
        output.append(
            {
                "deduction_id": str(deduction.get("deduction_id") or ""),
                "dimension": str(deduction.get("dimension") or ""),
                "severity": str(deduction.get("severity") or "medium"),
                "issue_type": str(deduction.get("issue_type") or "other"),
                "root_cause_stage": str(deduction.get("root_cause_stage") or ""),
                "optimization_classification": normalize_optimization_classification(
                    deduction, evaluation_issue_category
                ),
                "finding": str(deduction.get("finding") or ""),
                # 下列字段仅供 Markdown 组装使用；由 OpenAttributionDeduction
                # 响应模型过滤，不改变既有结构化字段的外部契约。
                "evidence_summary": str(deduction.get("evidence_summary") or ""),
                "observed_gap": _record(deduction.get("observed_gap")),
                "impact": str(deduction.get("impact") or ""),
                "primary_cause": _record(deduction.get("primary_cause")),
                "root_cause_test": _record(deduction.get("root_cause_test")),
                "rag_diagnosis": _record(deduction.get("rag_diagnosis")),
                "recommendations": _agent_recommendations(deduction.get("recommendations")),
            }
        )
    return output


def _agent_clusters(items: list[AttributionTaskItem]) -> tuple[int, list[dict[str, Any]]]:
    summary = build_task_diagnostic_summary(
        (item.sample_id, item.analysis_json) for item in items
    )
    clusters = []
    for cluster in summary.get("clusters") or []:
        if cluster.get("category") != "cx_agent_issue":
            continue
        projected = dict(cluster)
        projected["recommendations"] = _agent_recommendations(cluster.get("recommendations"))
        clusters.append(projected)
    affected_cases = {
        sample_id
        for cluster in clusters
        for sample_id in cluster.get("sample_ids") or []
    }
    return len(affected_cases), clusters


def _unique_recommendations(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按优先级保留可执行建议，避免 Markdown 中重复同一动作。"""
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    ordered = sorted(
        values,
        key=lambda value: priority_order.get(str(value.get("priority") or "P2").upper(), 2),
    )
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for value in ordered:
        target = str(value.get("target") or "").strip()
        action = str(value.get("action") or "").strip()
        key = (target, action)
        if not action or key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def _priority_for_deduction(deduction: dict[str, Any]) -> str:
    priorities = [
        str(item.get("priority") or "").upper()
        for item in deduction.get("recommendations") or []
        if isinstance(item, dict) and str(item.get("priority") or "").upper() in _PRIORITY_ORDER
    ]
    if priorities:
        return min(priorities, key=_PRIORITY_ORDER.index)
    severity = str(deduction.get("severity") or "").lower()
    if severity == "critical":
        return "P0"
    if severity == "high":
        return "P1"
    return "P2"


def _deduction_category_label(deduction: dict[str, Any]) -> str:
    classification = _record(deduction.get("optimization_classification"))
    _, primary_label, secondary_label = current_optimization_category(classification)
    return f"{primary_label} / {secondary_label}"


def _markdown_evidence(deduction: dict[str, Any]) -> list[str]:
    observed_gap = _record(deduction.get("observed_gap"))
    values = [str(deduction.get("evidence_summary") or "").strip()]
    values.extend(
        str(value or "").strip()
        for value in observed_gap.get("direct_evidence") or []
    )
    evidence = list(dict.fromkeys(value for value in values if value))
    return evidence or ["暂无可引用的直接证据"]


def _cx_agent_optimization_markdown(
    *,
    summary: str,
    deductions: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> str:
    """按归因详情页的八维/优先级/问题分类层级输出修复 Markdown。"""
    lines = [
        "# CX-Agent 归因结论与优化建议",
        "",
        "仅展示存在优化点的维度；每个维度内按 P0/P1/P2 和一级/二级问题分类展示。",
    ]

    if not deductions and not recommendations:
        lines.extend(["", "当前 Case 未发现可确认归责给 CX-Agent 的优化项。"])
        return "\n".join(lines)

    deductions_by_dimension = {
        dimension: [item for item in deductions if item.get("dimension") == dimension]
        for dimension in _DIMENSION_ORDER
    }
    unknown_deductions = [
        item for item in deductions if item.get("dimension") not in _DIMENSION_ORDER
    ]
    ordered_dimensions = [
        (dimension_index, dimension, _DIMENSION_LABELS[dimension], deductions_by_dimension[dimension])
        for dimension_index, dimension in enumerate(_DIMENSION_ORDER, start=1)
        if deductions_by_dimension[dimension]
    ]
    if unknown_deductions:
        ordered_dimensions.append((0, "other", "其他维度", unknown_deductions))

    for dimension_index, _, dimension_label, dimension_deductions in ordered_dimensions:
        dimension_number = f"{dimension_index:02d}" if dimension_index else "—"
        lines.extend(
            [
                "",
                f"## {dimension_number} {dimension_label}",
            ]
        )
        for priority in _PRIORITY_ORDER:
            priority_deductions = [
                item
                for item in dimension_deductions
                if _priority_for_deduction(item) == priority
            ]
            if not priority_deductions:
                continue
            lines.extend(
                [
                    "",
                    f"### {priority} · {_PRIORITY_LABELS[priority]}（{len(priority_deductions)} 个问题）",
                ]
            )
            for deduction in priority_deductions:
                finding = str(deduction.get("finding") or "问题描述待补充").strip()
                impact = str(deduction.get("impact") or "").strip()
                if not impact:
                    impact = str(
                        _record(deduction.get("observed_gap")).get("gap") or finding
                    ).strip()
                lines.extend(
                    [
                        "",
                        f"#### 问题分类：{_deduction_category_label(deduction)}",
                        f"- 问题描述：{finding}",
                        "- 直接证据：",
                    ]
                )
                lines.extend(f"  - {evidence}" for evidence in _markdown_evidence(deduction))
                lines.append(f"- 导致问题：{impact or '影响待补充'}")
                lines.append("- 怎么优化：")
                deduction_recommendations = _unique_recommendations(
                    list(deduction.get("recommendations") or [])
                )
                if deduction_recommendations:
                    for recommendation in deduction_recommendations:
                        lines.append(
                            f"  1. {str(recommendation.get('action') or '').strip()}"
                        )
                else:
                    lines.append("  1. 请根据问题分类补充具体、可执行的 CX-Agent 修复动作。")

    global_recommendations = _unique_recommendations(recommendations)
    if global_recommendations:
        lines.extend(["", "## 通用优化动作（未归属维度）"])
        for recommendation in global_recommendations:
            priority = str(recommendation.get("priority") or "P2").upper()
            target = str(recommendation.get("target") or "CX-Agent").strip()
            action = str(recommendation.get("action") or "").strip()
            lines.append(f"- [{priority}] {target}：{action}")
    return "\n".join(lines)


def list_open_attribution_tasks(
    session: Session,
    *,
    run_id: int | None,
    status: str | None,
    limit: int,
    offset: int,
    frontend_url: str,
) -> tuple[int, list[dict[str, Any]]]:
    """批量读取归因任务及其 cx-agent 优化投影，避免逐任务/逐 Case 的 N+1 查询。"""
    stmt = (
        select(AttributionTask, EvalRun.name)
        .join(EvalRun, EvalRun.id == AttributionTask.run_id)
        .order_by(AttributionTask.id.desc())
    )
    count_stmt = select(func.count(AttributionTask.id))
    if run_id is not None:
        stmt = stmt.where(AttributionTask.run_id == run_id)
        count_stmt = count_stmt.where(AttributionTask.run_id == run_id)
    if status is not None:
        stmt = stmt.where(AttributionTask.status == status)
        count_stmt = count_stmt.where(AttributionTask.status == status)

    total = int(session.scalar(count_stmt) or 0)
    pairs = list(session.execute(stmt.offset(offset).limit(limit)).all())
    if not pairs:
        return total, []

    tasks = [pair[0] for pair in pairs]
    task_ids = [task.id for task in tasks]
    rows_by_task: dict[int, list[AttributionTaskItem]] = defaultdict(list)
    items = list(
        session.scalars(
            select(AttributionTaskItem)
            .where(AttributionTaskItem.task_id.in_(task_ids))
            .order_by(AttributionTaskItem.task_id.desc(), AttributionTaskItem.id)
        )
    )
    for item in items:
        rows_by_task[item.task_id].append(item)

    case_pairs = list(
        session.execute(
            select(CaseResultRow.run_id, CaseResultRow)
            .where(
                CaseResultRow.run_id.in_([task.run_id for task in tasks]),
                CaseResultRow.sample_id.in_([item.sample_id for item in items]),
            )
        ).all()
    )
    cases_by_run_and_sample = {
        (run_id_value, row.sample_id): row for run_id_value, row in case_pairs
    }

    base_url = frontend_url.rstrip("/")
    output: list[dict[str, Any]] = []
    for task, run_name in pairs:
        task_items = rows_by_task[task.id]
        analyzed_case_count, clusters = _agent_clusters(task_items)
        case_outputs = []
        for item in task_items:
            analysis = _analysis(item.analysis_json)
            case_row = cases_by_run_and_sample.get((task.run_id, item.sample_id))
            deductions = _agent_deductions(analysis)
            recommendations = _agent_recommendations(analysis.get("global_recommendations"))
            summary_parts = [
                str(deduction.get("finding") or "").strip()
                for deduction in deductions
                if str(deduction.get("finding") or "").strip()
            ]
            if not summary_parts:
                summary_parts = [
                    str(recommendation.get("action") or "").strip()
                    for recommendation in recommendations
                    if str(recommendation.get("action") or "").strip()
                ]
            summary = "；".join(dict.fromkeys(summary_parts[:3]))
            case_outputs.append(
                {
                    "sample_id": item.sample_id,
                    "case_report_url": (
                        f"{base_url}/runs/{task.run_id}/attribution-tasks/{task.id}/cases/"
                        f"{quote(item.sample_id, safe='')}"
                    ),
                    "case_evaluation_url": (
                        f"{base_url}/runs/{task.run_id}/cases/"
                        f"{quote(item.sample_id, safe='')}"
                    ),
                    "evaluation_markdown": (
                        build_case_evaluation_markdown(case_row.detail_json)
                        if case_row is not None
                        else ""
                    ),
                    "scenario": case_row.scenario if case_row is not None else "",
                    "case_type": case_row.case_type if case_row is not None else "",
                    "status": item.status,
                    "attempt_count": int(item.attempt_count or 0),
                    "error_msg": item.error_msg or "",
                    "attribution_available": bool(_record(item.analysis_json).get("available")),
                    "started_at": item.started_at,
                    "finished_at": item.finished_at,
                    "cx_agent_optimization": {
                        "summary": summary,
                        "deductions": deductions,
                        "recommendations": recommendations,
                        "markdown": _cx_agent_optimization_markdown(
                            summary=summary,
                            deductions=deductions,
                            recommendations=recommendations,
                        ),
                    },
                }
            )
        output.append(
            {
                "id": task.id,
                "run_id": task.run_id,
                "run_name": run_name or "",
                "report_url": f"{base_url}/runs/{task.run_id}/attribution-tasks/{task.id}",
                "judge_model_id": task.judge_model_id,
                "judge_model_name": task.judge_model_name or "",
                "status": task.status,
                "requested_count": task.requested_count,
                "total_count": task.total_count,
                "skipped_count": task.skipped_count,
                "completed_count": task.completed_count,
                "success_count": task.success_count,
                "failed_count": task.failed_count,
                "error_msg": task.error_msg or "",
                "created_at": task.created_at,
                "started_at": task.started_at,
                "finished_at": task.finished_at,
                "cx_agent_optimization_summary": {
                    "cx_agent_case_count": analyzed_case_count,
                    "clusters": clusters,
                },
                "cases": case_outputs,
            }
        )
    return total, output
