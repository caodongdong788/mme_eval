"""面向 Open API 的归因任务只读投影。

归因原始结果还包含评测判据/判分工具的复核信息；该投影只暴露已经确认的
cx-agent 优化项，避免调用方把评测侧待复核信息误当作 Agent 缺陷处理。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models_db import AttributionTask, AttributionTaskItem, CaseResultRow, EvalRun
from .attribution_summary import build_task_diagnostic_summary, recommendation_category


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _analysis(value: Any) -> dict[str, Any]:
    return _record(_record(value).get("analysis"))


def _agent_recommendations(values: Any) -> list[dict[str, Any]]:
    return [
        dict(value)
        for value in values or []
        if isinstance(value, dict) and recommendation_category(value) == "cx_agent_issue"
    ]


def _agent_deductions(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """仅保留有证据支持、可归责给 cx-agent 的扣分项。"""
    output: list[dict[str, Any]] = []
    for deduction in analysis.get("deduction_analyses") or []:
        if not isinstance(deduction, dict):
            continue
        if deduction.get("deduction_validation") != "supported":
            continue
        output.append(
            {
                "deduction_id": str(deduction.get("deduction_id") or ""),
                "dimension": str(deduction.get("dimension") or ""),
                "severity": str(deduction.get("severity") or "medium"),
                "issue_type": str(deduction.get("issue_type") or "other"),
                "root_cause_stage": str(deduction.get("root_cause_stage") or ""),
                "finding": str(deduction.get("finding") or ""),
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
            case_outputs.append(
                {
                    "sample_id": item.sample_id,
                    "scenario": case_row.scenario if case_row is not None else "",
                    "case_type": case_row.case_type if case_row is not None else "",
                    "status": item.status,
                    "attempt_count": int(item.attempt_count or 0),
                    "error_msg": item.error_msg or "",
                    "attribution_available": bool(_record(item.analysis_json).get("available")),
                    "started_at": item.started_at,
                    "finished_at": item.finished_at,
                    "cx_agent_optimization": {
                        "summary": "；".join(dict.fromkeys(summary_parts[:3])),
                        "deductions": deductions,
                        "recommendations": recommendations,
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
