"""评测工具问题的稳定分类。

新归因结果优先采用模型返回的结构化分类；旧归因结果没有该字段时，使用保守的
中文语义规则补分类，确保历史任务无需重跑也能拆分展示。
"""

from __future__ import annotations

import re
from typing import Any


EVALUATION_ISSUE_CATEGORIES = {
    "none",
    "benchmark_criteria_conflict",
    "annotation_rag_conflict",
    "judge_logic_issue",
    "missing_rag_reference",
    # evidence_gap 表示非 RAG 的通用证据缺失，与缺少 RAG 引用分开处理。
    "evidence_gap",
}


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _analysis_text(deduction: dict[str, Any]) -> str:
    cause = _record(deduction.get("primary_cause"))
    observed = _record(deduction.get("observed_gap"))
    rag = _record(deduction.get("rag_diagnosis"))
    values: list[Any] = [
        deduction.get("finding"),
        cause.get("label"),
        cause.get("reason"),
        observed.get("expected"),
        observed.get("actual"),
        observed.get("gap"),
        rag.get("finding"),
    ]
    for recommendation in deduction.get("recommendations") or []:
        if isinstance(recommendation, dict):
            values.extend((recommendation.get("target"), recommendation.get("action")))
    return " ".join(str(value or "") for value in values)


def classify_evaluation_issue(deduction: dict[str, Any]) -> str:
    """返回互斥的问题分类，避免把 cx-agent 缺陷误归为评测工具问题。"""
    validation = str(deduction.get("deduction_validation") or "")
    if validation == "supported":
        return "none"
    explicit = str(deduction.get("evaluation_issue_category") or "")
    if validation == "insufficient_evidence":
        # Rubric 是独立的评测真值，不能因其没有绑定 RAG 就要求补文献。
        # 只有该项本来依赖 RAG 审计、却缺少可回链的召回原文/引用映射时，
        # 才使用 missing_rag_reference；其他证据缺失保持 evidence_gap。
        if explicit in {"missing_rag_reference", "evidence_gap"}:
            return explicit
        return "evidence_gap"

    if explicit == "evidence_gap":
        return "evidence_gap"
    if explicit in EVALUATION_ISSUE_CATEGORIES - {"none", "evidence_gap"}:
        return explicit
    if validation != "questionable":
        return "evidence_gap"

    text = _analysis_text(deduction)
    internal_benchmark_conflict = re.search(
        r"自身参考答案|参考答案中|判据.{0,24}(?:参考答案|执行提示).{0,12}(?:冲突|矛盾)|"
        r"(?:参考答案|执行提示).{0,24}判据.{0,12}(?:冲突|矛盾)|"
        r"规则重叠|重复规则|重复扣分|重复计罚|近同义规则|同一证据包.{0,20}(?:相反|不一致)",
        text,
        re.IGNORECASE,
    )
    if internal_benchmark_conflict:
        return "benchmark_criteria_conflict"

    conflict = re.search(
        r"冲突|矛盾|不一致|相反|自相矛盾|不支持|未覆盖|无法证明|不能证明|"
        r"证据越界|过度外推|口径不同|口径不一",
        text,
        re.IGNORECASE,
    )
    evaluation_truth = re.search(
        r"标注|真值|判据|评分规则|扣分规则|参考答案|好答案|benchmark|rubric",
        text,
        re.IGNORECASE,
    )
    rag_evidence = re.search(
        r"\bRAG\b|检索|召回|文献|说明书|医学证据|入选资料|选中文献|"
        r"引用支持|来源证据|现有来源|当前来源",
        text,
        re.IGNORECASE,
    )
    if conflict and evaluation_truth and rag_evidence:
        return "annotation_rag_conflict"

    benchmark_contract = re.search(
        r"判据|检查点|扣分规则|评分规则|参考答案|好答案|适用条件|触发条件|"
        r"benchmark|rubric|重复扣分|重复规则|规则重叠",
        text,
        re.IGNORECASE,
    )
    if conflict and benchmark_contract:
        return "benchmark_criteria_conflict"
    return "judge_logic_issue"
