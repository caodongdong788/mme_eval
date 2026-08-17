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


_SEVERITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}
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
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        if not isinstance(value, dict):
            continue
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
    text = f"{item.get('target') or ''} {item.get('action') or ''}"
    if re.search(r"benchmark|judge|评测|判分|判据|评分", text, re.IGNORECASE):
        return "evaluation_review"
    if re.search(r"证据采集|调用链|链路|审计|可观测|trace|observability", text, re.IGNORECASE):
        return "insufficient_evidence"
    return "cx_agent_issue"


def _normalized_label(value: Any) -> str:
    """保留业务根因语义，只消除空白/标点差异，避免不同问题被错误合并。"""
    return re.sub(r"[\s，,。；;：:]+", " ", str(value or "原因待确认")).strip().lower()


def _priority(case_count: int, severities: list[str], category: str) -> str:
    strongest = max((_SEVERITY_WEIGHT.get(value, 2) for value in severities), default=2)
    if category == "cx_agent_issue" and strongest >= 4:
        return "P0"
    if case_count >= 3 or strongest >= 3:
        return "P1"
    return "P2"


def _rag_optimization_category(deduction: dict[str, Any], evaluation_issue_category: str) -> str:
    """将结构化 RAG 诊断归入可执行的优化方向。

    不从自由文本猜测，优先使用 primary_cause.code 和 rag_diagnosis 的枚举值；
    汇总页与单 Case 页因此可以稳定地展示同一套 RAG 优化分类。
    """
    if evaluation_issue_category == "missing_rag_reference":
        return "missing_rag_reference"
    cause = _record(deduction.get("primary_cause"))
    code = str(cause.get("code") or "").lower()
    diagnosis = _record(deduction.get("rag_diagnosis"))
    status = str(diagnosis.get("diagnosis") or "").lower()
    query_quality = str(diagnosis.get("query_quality") or "").lower()
    answer_usage = str(diagnosis.get("answer_usage") or "").lower()

    if code == "rag_not_called" or status == "not_called":
        return "rag_not_called"
    if code == "rag_call_failed" or status == "failed":
        return "rag_call_failed"
    if code == "rag_query_error" or status == "query_error" or query_quality in {"incomplete", "wrong"}:
        return "rag_query_error"
    if code == "rag_corpus_gap" or status == "corpus_gap":
        return "rag_corpus_gap"
    if code == "rag_recall_error" or status == "recall_error":
        return "rag_recall_error"
    if code == "rag_threshold_error" or status == "threshold_error":
        return "rag_threshold_error"
    if code in {"rag_candidate_or_rerank_error", "rag_rerank_error"} or status in {
        "candidate_or_rerank_error",
        "rerank_error",
    }:
        return "rag_rerank_error"
    if code == "rag_not_grounded" or status == "selected_not_used" or answer_usage == "not_used":
        return "rag_not_grounded"
    if code == "rag_misinterpreted" or status == "selected_misinterpreted" or answer_usage in {
        "misinterpreted",
        "unsupported_claim",
    }:
        return "rag_misinterpreted"
    return ""


def build_task_diagnostic_summary(
    items: Iterable[tuple[str, dict[str, Any] | None]],
) -> dict[str, Any]:
    """按复核结论 + 根因 + 责任模块聚合一批 Case。"""
    health_counts: Counter[str] = Counter()
    validation_counts: Counter[str] = Counter()
    clusters: dict[tuple[str, str, str, str, str, str, str, str], dict[str, Any]] = {}
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
            rag_optimization_category = _rag_optimization_category(
                deduction, evaluation_issue_category
            )
            cause = _record(deduction.get("primary_cause"))
            code = str(cause.get("code") or "insufficient_evidence")
            owner = str(cause.get("owner") or "unknown")
            issue_type = str(deduction.get("issue_type") or "other")
            root_cause_stage = str(deduction.get("root_cause_stage") or "unknown")
            cause_label = str(cause.get("label") or "原因待确认")
            key = (
                category,
                evaluation_issue_category,
                code,
                owner,
                issue_type,
                root_cause_stage,
                rag_optimization_category,
                _normalized_label(cause_label),
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
                    "rag_optimization_category": rag_optimization_category,
                    "issue_types": [],
                    "sample_ids": [],
                    "deduction_ids": [],
                    "dimensions": [],
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
            dimension = str(deduction.get("dimension") or "")
            if dimension and dimension not in cluster["dimensions"]:
                cluster["dimensions"].append(dimension)
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
                "priority": _priority(case_count, severities, category),
                "confidence": round(
                    sum(confidence_values) / len(confidence_values), 3
                ) if confidence_values else 0.0,
                "summary": findings[0] if findings else "暂无可展示的根因摘要",
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
