"""归因任务的跨 Case 聚合诊断。

单 Case 归因回答“这条为什么失败”；本模块把相同责任环节和根因合并，
让任务页面直接回答“最值得先修的系统性问题是什么、影响多少 Case、应该怎么优化”。
聚合只使用已经落库的结构化归因，不再额外调用模型。
"""

from __future__ import annotations

from collections import Counter
import re
from typing import Any, Iterable

from .attribution_issue_categories import classify_evaluation_issue
from .attribution_taxonomy import normalize_optimization_classification


_SEVERITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}
_PRIORITY_WEIGHT = {"P0": 0, "P1": 1, "P2": 2}
_VALIDATION_CATEGORY = {
    "supported": "cx_agent_issue",
    "questionable": "evaluation_review",
    "insufficient_evidence": "insufficient_evidence",
}


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _analysis(value: Any) -> dict[str, Any]:
    wrapper = _record(value)
    return _record(wrapper.get("analysis"))


def _recommendation_key(item: dict[str, Any]) -> tuple[str, str]:
    return (str(item.get("target") or ""), str(item.get("action") or ""))


def _unique_recommendations(values: Iterable[Any], limit: int = 8) -> list[dict[str, Any]]:
    ordered = sorted(
        (value for value in values if isinstance(value, dict)),
        key=lambda item: _PRIORITY_WEIGHT.get(
            str(item.get("priority") or "P2").upper(), 2
        ),
    )
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for value in ordered:
        key = _recommendation_key(value)
        if not any(key) or key in seen:
            continue
        seen.add(key)
        output.append(value)
        if len(output) >= limit:
            break
    return output


def recommendation_category(item: dict[str, Any]) -> str:
    """按优化目标归类建议，供任务汇总和 Open API 使用。"""
    scope = str(item.get("scope") or "").lower()
    if scope == "evaluation":
        return "evaluation_review"
    if scope == "evidence":
        return "insufficient_evidence"
    if scope == "cx_agent":
        return "cx_agent_issue"
    # 仅为旧数据保留文本兜底；新归因结果全部使用结构化 scope。
    text = f"{item.get('target') or ''} {item.get('action') or ''}"
    if re.search(r"benchmark|judge|评测|判分|判据|评分", text, re.IGNORECASE):
        return "evaluation_review"
    if re.search(r"证据采集|调用链|链路|审计|可观测|trace|observability", text, re.IGNORECASE):
        return "insufficient_evidence"
    return "cx_agent_issue"


def _normalized_label(value: Any) -> str:
    """只消除空白和标点差异，不从文本推断责任模块。"""
    return re.sub(r"[\s，,。；;：:]+", " ", str(value or "原因待确认")).strip().lower()


def _priority(
    case_count: int,
    severities: list[str],
    category: str,
    recommendations: list[dict[str, Any]],
) -> str:
    recommended = [
        str(item.get("priority") or "").upper()
        for item in recommendations
        if str(item.get("priority") or "").upper() in _PRIORITY_WEIGHT
    ]
    strongest = max((_SEVERITY_WEIGHT.get(value, 2) for value in severities), default=2)
    if category == "cx_agent_issue" and strongest >= 4:
        inferred = "P0"
    elif case_count >= 3 or strongest >= 3:
        inferred = "P1"
    else:
        inferred = "P2"
    return min([inferred, *recommended], key=lambda value: _PRIORITY_WEIGHT[value])


def _common_problem_summary(cause_label: str, findings: list[str]) -> str:
    if not findings:
        return cause_label or "暂无可展示的根因摘要"
    if len(findings) == 1:
        return findings[0]
    return (
        f"共同问题为“{cause_label or '同类失败节点'}”。"
        f"代表性表现：{findings[0]}"
    )


def build_task_diagnostic_summary(
    items: Iterable[tuple[str, dict[str, Any] | None]],
) -> dict[str, Any]:
    """按复核结论 + 根因 + 责任模块聚合一批 Case。"""
    health_counts: Counter[str] = Counter()
    validation_counts: Counter[str] = Counter()
    clusters: dict[tuple[str, ...], dict[str, Any]] = {}
    available_results = 0

    for sample_id, stored in items:
        analysis = _analysis(stored)
        if not analysis:
            continue
        available_results += 1
        health = str(_record(analysis.get("score_health")).get("status") or "unknown")
        health_counts[health] += 1
        for deduction in analysis.get("deduction_analyses") or []:
            if not isinstance(deduction, dict):
                continue
            validation = str(deduction.get("deduction_validation") or "insufficient_evidence")
            validation_counts[validation] += 1
            evaluation_issue_category = classify_evaluation_issue(deduction)
            # “缺少 RAG 引用”说明 cx-agent 没有把本应提供的检索依据
            # 映射到回答，属于 RAG 优化项，不归入评测工具待复核。
            category = (
                "cx_agent_issue"
                if evaluation_issue_category == "missing_rag_reference"
                else _VALIDATION_CATEGORY.get(validation, "insufficient_evidence")
            )
            optimization_classification = normalize_optimization_classification(
                deduction, evaluation_issue_category
            )
            # 结构化分类是最终责任边界：评测系统问题不得混入 cx-agent，
            # 新增但尚未纳入分类表的根因也不得伪装成已确认的 Agent 缺陷。
            if optimization_classification["domain"] == "evaluation_system":
                category = "evaluation_review"
            elif optimization_classification.get("coverage_status") == "unmapped":
                category = "insufficient_evidence"
            cause = _record(deduction.get("primary_cause"))
            code = str(cause.get("code") or "insufficient_evidence")
            owner = str(cause.get("owner") or "unknown")
            issue_type = str(deduction.get("issue_type") or "other")
            root_cause_stage = str(deduction.get("root_cause_stage") or "unknown")
            cause_label = str(cause.get("label") or "原因待确认")
            dimension = str(deduction.get("dimension") or "")
            key = (
                dimension,
                category,
                evaluation_issue_category,
                code,
                _normalized_label(cause_label),
                owner,
                issue_type,
                root_cause_stage,
                optimization_classification.get("category_primary", ""),
                optimization_classification.get("category_secondary", ""),
                optimization_classification["domain"],
                optimization_classification["component"],
                optimization_classification["failure_mode"],
                optimization_classification["action_type"],
            )
            cluster = clusters.setdefault(
                key,
                {
                    "category": category,
                    "evaluation_issue_category": evaluation_issue_category,
                    "cause_code": code,
                    "cause_label": cause_label,
                    "owner": owner,
                    "root_cause_stage": root_cause_stage,
                    "optimization_classification": optimization_classification,
                    "issue_types": [],
                    "sample_ids": [],
                    "deduction_ids": [],
                    "dimensions": [dimension] if dimension else [],
                    "severities": [],
                    "confidences": [],
                    "findings": [],
                    "recommendations": [],
                    "verification_plans": [],
                },
            )
            if issue_type not in cluster["issue_types"]:
                cluster["issue_types"].append(issue_type)
            if sample_id not in cluster["sample_ids"]:
                cluster["sample_ids"].append(sample_id)
            deduction_id = str(deduction.get("deduction_id") or "")
            if deduction_id:
                cluster["deduction_ids"].append(deduction_id)
            cluster["severities"].append(str(deduction.get("severity") or "medium"))
            try:
                cluster["confidences"].append(float(cause.get("confidence") or 0))
            except (TypeError, ValueError):
                pass
            finding = str(deduction.get("finding") or cause.get("reason") or "")
            if finding and finding not in cluster["findings"]:
                cluster["findings"].append(finding)
            cluster["recommendations"].extend(
                item for item in deduction.get("recommendations") or []
                if isinstance(item, dict) and recommendation_category(item) == category
            )
            verification = _record(analysis.get("verification_plan"))
            if verification:
                cluster["verification_plans"].append(verification)

    output_clusters: list[dict[str, Any]] = []
    for cluster in clusters.values():
        case_count = len(cluster["sample_ids"])
        category = cluster["category"]
        plans = cluster.pop("verification_plans")
        combined_plan = {
            "target_cases": cluster["sample_ids"][:20],
            "control_cases": list(dict.fromkeys(
                str(value)
                for plan in plans
                for value in plan.get("control_cases") or []
            ))[:10],
            "safety_checks": list(dict.fromkeys(
                str(value)
                for plan in plans
                for value in plan.get("safety_checks") or []
            ))[:10],
            "acceptance_criteria": list(dict.fromkeys(
                str(value)
                for plan in plans
                for value in plan.get("acceptance_criteria") or []
            ))[:10],
        }
        confidence_values = cluster.pop("confidences")
        severities = cluster.pop("severities")
        recommendations = cluster.pop("recommendations")
        findings = cluster.pop("findings")
        cluster.update(
            {
                "issue_type": (
                    cluster["issue_types"][0]
                    if len(cluster["issue_types"]) == 1
                    else "multiple"
                ),
                "case_count": case_count,
                "deduction_count": len(cluster["deduction_ids"]),
                "priority": _priority(
                    case_count, severities, category, recommendations
                ),
                "confidence": round(
                    sum(confidence_values) / len(confidence_values), 3
                ) if confidence_values else 0.0,
                "summary": _common_problem_summary(
                    str(cluster.get("cause_label") or ""), findings
                ),
                "examples": findings[:3],
                "recommendations": _unique_recommendations(recommendations),
                "verification_plan": combined_plan,
            }
        )
        output_clusters.append(cluster)

    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    category_order = {"cx_agent_issue": 0, "evaluation_review": 1, "insufficient_evidence": 2}
    output_clusters.sort(
        key=lambda item: (
            category_order.get(item["category"], 9),
            priority_order.get(item["priority"], 9),
            -item["case_count"],
            item["cause_label"],
        )
    )
    return {
        "available_results": available_results,
        "score_health_counts": dict(health_counts),
        "validation_counts": dict(validation_counts),
        "clusters": output_clusters,
    }
