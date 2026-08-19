"""cx-agent 归因优化的稳定分类体系。

归因模型负责判断事实和根因；本模块负责把根因落到与 cx-agent 代码结构一致的
一级领域、具体组件和优化动作。分类只依赖结构化枚举，不从中文建议文本猜测。
"""

from __future__ import annotations

from typing import Any


DOMAIN_LABELS = {
    "medical_safety": "医学安全与策略",
    "prompt_hook": "Prompt、Hook 与专家配置",
    "context_memory": "用户上下文与长期记忆",
    "dialogue_tool_orchestration": "对话与工具编排",
    "medical_rag": "医学文献 RAG",
    "clinical_reasoning": "临床推理与方案合成",
    "response_delivery": "回答生成与交付协议",
    "model_runtime_observability": "模型运行时与可观测性",
    "evaluation_system": "评测系统复核",
}

COMPONENT_LABELS = {
    "safety_policy": "医学安全策略",
    "static_prompt": "静态 Prompt",
    "dynamic_hook": "动态 Hook / Reminder",
    "expert_pack": "专家配置",
    "structured_profile": "用户结构化档案",
    "medical_record": "病历与医学指标",
    "timeline": "Timeline 长期事实",
    "chat_history": "历史对话",
    "saved_content": "病例夹与已保存资料",
    "consult_subject": "咨询对象归属",
    "context_usage": "上下文利用",
    "context_conflict": "上下文新旧冲突",
    "memory_write": "长期记忆写入与维护",
    "intent_routing": "意图与流程路由",
    "clarification": "追问与澄清策略",
    "feature_gate": "能力开关",
    "tool_registry": "工具注册与可见性",
    "tool_selection": "工具选择",
    "tool_arguments": "工具参数",
    "tool_policy": "工具调用策略",
    "tool_executor": "工具执行",
    "proactive_undercurrent": "主动服务与暗流 Agent",
    "rag_trigger": "RAG 触发决策",
    "rag_service": "RAG 服务调用",
    "rag_query": "检索问题改写",
    "rag_corpus": "医学知识库",
    "rag_retrieval": "原始召回",
    "rag_threshold": "阈值与过滤",
    "rag_candidate": "候选文献生成",
    "rag_rerank": "候选重排",
    "rag_grounding": "召回证据利用",
    "rag_interpretation": "医学证据理解",
    "citation_binding": "引用绑定",
    "clinical_fact_extraction": "临床事实提取",
    "temporal_reasoning": "时间线推理",
    "risk_benefit": "风险收益权衡",
    "contraindication": "禁忌与相互作用",
    "clinical_synthesis": "临床方案合成",
    "content_composition": "回答内容组织",
    "response_completeness": "回答完整性",
    "response_style": "表达与沟通风格",
    "output_protocol": "终答输出协议",
    "a2ui_binding": "A2UI 与资源绑定",
    "delivery_ui": "SSE 与前端交付",
    "model_provider": "模型供应商调用",
    "model_timeout": "模型流式超时",
    "partial_output": "模型部分或空输出",
    "context_window": "上下文窗口",
    "compaction": "上下文压缩",
    "tool_result_budget": "工具结果预算与截断",
    "observability_evidence": "调用链与证据采集",
    "taxonomy_gap": "归因分类待补充",
    "benchmark": "Benchmark 判据",
    "judge": "判分模型",
    "unknown": "待确认组件",
}

ACTION_TYPE_LABELS = {
    "safety_rule": "调整安全策略",
    "prompt_rule": "调整静态 Prompt",
    "hook_rule": "调整动态 Hook / Reminder",
    "expert_pack": "调整专家配置",
    "context_injection": "调整上下文注入与读取",
    "memory_pipeline": "调整长期记忆链路",
    "dialogue_policy": "调整对话策略",
    "tool_schema": "调整工具 Schema 与路由说明",
    "feature_gate": "调整能力开关",
    "tool_executor": "修复工具执行链路",
    "rag_trigger": "调整 RAG 触发策略",
    "rag_query": "调整检索问题",
    "rag_service": "修复 RAG 服务调用",
    "rag_corpus": "补充或更新知识库",
    "retrieval_config": "调整召回策略",
    "threshold_config": "调整阈值与过滤",
    "rerank_config": "调整候选与重排",
    "grounding_rule": "调整证据利用规则",
    "citation_binding": "修复引用绑定",
    "clinical_reasoning": "调整临床推理规则",
    "response_composition": "调整回答生成",
    "response_protocol": "修复终答协议",
    "delivery_ui": "修复交付与渲染链路",
    "model_config": "调整模型配置",
    "runtime_resilience": "增强运行时重试与降级",
    "observability": "补充可观测证据",
    "evaluation_rule": "修正 Benchmark 判据",
    "judge_logic": "修正判分逻辑",
    "unknown": "确认后制定优化动作",
}

DOMAIN_COMPONENTS = {
    "medical_safety": {"safety_policy"},
    "prompt_hook": {"static_prompt", "dynamic_hook", "expert_pack"},
    "context_memory": {
        "structured_profile", "medical_record", "timeline", "chat_history",
        "saved_content", "consult_subject", "context_usage", "context_conflict",
        "memory_write",
    },
    "dialogue_tool_orchestration": {
        "intent_routing", "clarification", "feature_gate", "tool_registry",
        "tool_selection", "tool_arguments", "tool_policy", "tool_executor",
        "proactive_undercurrent",
    },
    "medical_rag": {
        "rag_trigger", "rag_service", "rag_query", "rag_corpus", "rag_retrieval",
        "rag_threshold", "rag_candidate", "rag_rerank", "rag_grounding",
        "rag_interpretation", "citation_binding",
    },
    "clinical_reasoning": {
        "clinical_fact_extraction", "temporal_reasoning", "risk_benefit",
        "contraindication", "clinical_synthesis",
    },
    "response_delivery": {
        "content_composition", "response_completeness", "response_style",
        "output_protocol", "a2ui_binding", "delivery_ui",
    },
    "model_runtime_observability": {
        "model_provider", "model_timeout", "partial_output", "context_window",
        "compaction", "tool_result_budget", "observability_evidence",
        "taxonomy_gap",
    },
    "evaluation_system": {"benchmark", "judge"},
}

DOMAIN_ACTION_TYPES = {
    "medical_safety": {"safety_rule"},
    "prompt_hook": {"prompt_rule", "hook_rule", "expert_pack"},
    "context_memory": {"context_injection", "memory_pipeline"},
    "dialogue_tool_orchestration": {
        "dialogue_policy", "tool_schema", "feature_gate", "tool_executor"
    },
    "medical_rag": {
        "rag_trigger", "rag_query", "rag_service", "rag_corpus",
        "retrieval_config", "threshold_config", "rerank_config",
        "grounding_rule", "citation_binding",
    },
    "clinical_reasoning": {"clinical_reasoning"},
    "response_delivery": {"response_composition", "response_protocol", "delivery_ui"},
    "model_runtime_observability": {
        "model_config", "runtime_resilience", "observability"
    },
    "evaluation_system": {"evaluation_rule", "judge_logic"},
}


# 面向产品展示的一级、二级分类。它与归因详情页使用的分类口径一致，
# 内部 domain/component 仍用于代码定位，不直接暴露给业务用户。
DOCUMENT_CATEGORY_LABELS = {
    "rag": "RAG 优化",
    "engineering": "Agent 工程链路",
    "reasoning": "Agent 决策与推理策略",
    "prompt": "提示词与回答生成策略",
    "knowledge": "知识与规则内化",
    "safety": "输出校验与安全守卫",
}

_RAG_DOCUMENT_COMPONENTS = {
    "rag_trigger": "未触发检索",
    "rag_service": "调用失败",
    "rag_query": "Query 不完整或意图识别偏差",
    "rag_corpus": "召回覆盖不足",
    "rag_retrieval": "召回覆盖不足",
    "rag_threshold": "召回覆盖不足",
    "rag_candidate": "排序或重排不当",
    "rag_rerank": "排序或重排不当",
    "rag_grounding": "已召回但未使用",
    "rag_interpretation": "证据误读",
    "citation_binding": "缺少 RAG 引用",
}


def documented_optimization_category(domain: str, component: str) -> tuple[str, str, str]:
    """把内部归因位置映射为文档约定的一级、二级业务分类。"""
    if domain == "medical_rag":
        primary = "rag"
        secondary = _RAG_DOCUMENT_COMPONENTS.get(component, "召回覆盖不足")
    elif domain == "context_memory":
        primary = "engineering"
        if component in {"timeline", "structured_profile", "medical_record", "chat_history", "saved_content"}:
            secondary = "Timeline 或用户事实未注入"
        else:
            secondary = {
                "context_usage": "上下文已注入但未使用",
                "consult_subject": "咨询对象归属错误",
                "context_conflict": "上下文新旧冲突",
                "memory_write": "长期记忆写入失败",
            }.get(component, "多轮状态丢失")
    elif domain == "dialogue_tool_orchestration":
        if component == "clarification":
            primary, secondary = "reasoning", "未优先追问关键问题"
        else:
            primary = "engineering"
            secondary = {
                "tool_registry": "工具未调用",
                "tool_selection": "工具选择错误",
                "tool_arguments": "工具参数错误",
                "tool_policy": "工具执行失败",
                "tool_executor": "工具执行失败",
                "feature_gate": "能力开关未启用",
                "proactive_undercurrent": "主动服务链路异常",
            }.get(component, "流程路由错误")
    elif domain == "prompt_hook":
        if component == "expert_pack":
            primary, secondary = "knowledge", "专家规则未正确应用"
        else:
            primary = "prompt"
            secondary = (
                "动态 Hook 未触发或规则错误"
                if component == "dynamic_hook"
                else "系统提示词规则缺失或冲突"
            )
    elif domain == "clinical_reasoning":
        primary = "reasoning"
        secondary = {
            "clinical_fact_extraction": "关键医学事实识别错误",
            "temporal_reasoning": "Timeline 时间顺序判断错误",
            "risk_benefit": "风险识别不足",
            "contraindication": "禁忌或相互作用判断不足",
        }.get(component, "错误选择行动路径")
    elif domain == "response_delivery":
        if component in {"output_protocol"}:
            primary, secondary = "safety", "未执行终答前检查"
        elif component in {"a2ui_binding", "delivery_ui"}:
            primary, secondary = "engineering", "回答交付或资源绑定失败"
        else:
            primary = "prompt"
            secondary = {
                "response_style": "缺少共情与确认",
                "content_composition": "行动步骤不清晰",
                "response_completeness": "回答关键信息不完整",
            }.get(component, "缺少适用条件或解释")
    elif domain == "medical_safety":
        primary, secondary = "safety", "放出不安全建议"
    elif domain == "model_runtime_observability":
        primary = "engineering"
        secondary = {
            "model_provider": "模型调用失败",
            "model_timeout": "模型调用超时",
            "partial_output": "模型输出不完整",
            "context_window": "上下文窗口或压缩异常",
            "compaction": "上下文窗口或压缩异常",
            "tool_result_budget": "工具结果被截断",
            "observability_evidence": "调用链证据缺失",
        }.get(component, "模型运行时异常")
    else:
        primary, secondary = "engineering", "流程路由错误"
    return primary, DOCUMENT_CATEGORY_LABELS[primary], secondary

_CAUSE_CLASSIFICATION: dict[str, tuple[str, str, str]] = {
    "judge_or_benchmark_issue": ("evaluation_system", "judge", "judge_logic"),
    "safety_policy_error": ("medical_safety", "safety_policy", "safety_rule"),
    "prompt_rule_error": ("prompt_hook", "static_prompt", "prompt_rule"),
    "hook_rule_error": ("prompt_hook", "dynamic_hook", "hook_rule"),
    "expert_pack_error": ("prompt_hook", "expert_pack", "expert_pack"),
    "context_not_fetched": ("context_memory", "structured_profile", "context_injection"),
    "context_not_used": ("context_memory", "context_usage", "context_injection"),
    "context_subject_error": ("context_memory", "consult_subject", "context_injection"),
    "context_stale_or_conflict": ("context_memory", "context_conflict", "context_injection"),
    "memory_write_error": ("context_memory", "memory_write", "memory_pipeline"),
    "clarification_strategy_error": ("dialogue_tool_orchestration", "clarification", "dialogue_policy"),
    "intent_routing_error": ("dialogue_tool_orchestration", "intent_routing", "dialogue_policy"),
    "feature_gate_error": ("dialogue_tool_orchestration", "feature_gate", "feature_gate"),
    "tool_not_available": ("dialogue_tool_orchestration", "tool_registry", "tool_schema"),
    "tool_not_called": ("dialogue_tool_orchestration", "tool_selection", "tool_schema"),
    "tool_selection_error": ("dialogue_tool_orchestration", "tool_selection", "tool_schema"),
    "tool_argument_error": ("dialogue_tool_orchestration", "tool_arguments", "tool_schema"),
    "tool_blocked": ("dialogue_tool_orchestration", "tool_policy", "tool_executor"),
    "tool_execution_failed": ("dialogue_tool_orchestration", "tool_executor", "tool_executor"),
    "tool_timeout": ("dialogue_tool_orchestration", "tool_executor", "tool_executor"),
    "proactive_or_undercurrent_error": ("dialogue_tool_orchestration", "proactive_undercurrent", "dialogue_policy"),
    "rag_not_needed": ("medical_rag", "rag_trigger", "rag_trigger"),
    "rag_not_called": ("medical_rag", "rag_trigger", "rag_trigger"),
    "rag_call_failed": ("medical_rag", "rag_service", "rag_service"),
    "rag_query_error": ("medical_rag", "rag_query", "rag_query"),
    "rag_corpus_gap": ("medical_rag", "rag_corpus", "rag_corpus"),
    "rag_recall_error": ("medical_rag", "rag_retrieval", "retrieval_config"),
    "rag_threshold_error": ("medical_rag", "rag_threshold", "threshold_config"),
    "rag_candidate_or_rerank_error": ("medical_rag", "rag_candidate", "rerank_config"),
    "rag_rerank_error": ("medical_rag", "rag_rerank", "rerank_config"),
    "rag_not_grounded": ("medical_rag", "rag_grounding", "grounding_rule"),
    "rag_misinterpreted": ("medical_rag", "rag_interpretation", "grounding_rule"),
    "citation_mismatch": ("medical_rag", "citation_binding", "citation_binding"),
    "missing_rag_reference": ("medical_rag", "citation_binding", "citation_binding"),
    "reasoning_error": ("clinical_reasoning", "clinical_synthesis", "clinical_reasoning"),
    "clinical_fact_extraction_error": ("clinical_reasoning", "clinical_fact_extraction", "clinical_reasoning"),
    "temporal_reasoning_error": ("clinical_reasoning", "temporal_reasoning", "clinical_reasoning"),
    "risk_benefit_error": ("clinical_reasoning", "risk_benefit", "clinical_reasoning"),
    "contraindication_error": ("clinical_reasoning", "contraindication", "clinical_reasoning"),
    "response_composition_error": ("response_delivery", "content_composition", "response_composition"),
    "response_incomplete": ("response_delivery", "response_completeness", "response_composition"),
    "response_style_error": ("response_delivery", "response_style", "response_composition"),
    "output_protocol_error": ("response_delivery", "output_protocol", "response_protocol"),
    "a2ui_binding_error": ("response_delivery", "a2ui_binding", "response_protocol"),
    "delivery_render_error": ("response_delivery", "delivery_ui", "delivery_ui"),
    "model_api_error": ("model_runtime_observability", "model_provider", "runtime_resilience"),
    "model_timeout": ("model_runtime_observability", "model_timeout", "runtime_resilience"),
    "model_partial_output": ("model_runtime_observability", "partial_output", "runtime_resilience"),
    "context_window_error": ("model_runtime_observability", "context_window", "runtime_resilience"),
    "compaction_error": ("model_runtime_observability", "compaction", "runtime_resilience"),
    "tool_result_truncated": ("model_runtime_observability", "tool_result_budget", "runtime_resilience"),
    "observability_gap": ("model_runtime_observability", "observability_evidence", "observability"),
    "insufficient_evidence": ("model_runtime_observability", "observability_evidence", "observability"),
}

_RAG_DIAGNOSIS_CLASSIFICATION: dict[str, tuple[str, str, str, str]] = {
    "not_called": ("rag_not_called", "medical_rag", "rag_trigger", "rag_trigger"),
    "failed": ("rag_call_failed", "medical_rag", "rag_service", "rag_service"),
    "query_error": ("rag_query_error", "medical_rag", "rag_query", "rag_query"),
    "corpus_gap": ("rag_corpus_gap", "medical_rag", "rag_corpus", "rag_corpus"),
    "recall_error": ("rag_recall_error", "medical_rag", "rag_retrieval", "retrieval_config"),
    "threshold_error": ("rag_threshold_error", "medical_rag", "rag_threshold", "threshold_config"),
    "candidate_or_rerank_error": (
        "rag_candidate_or_rerank_error", "medical_rag", "rag_candidate", "rerank_config"
    ),
    "rerank_error": ("rag_rerank_error", "medical_rag", "rag_rerank", "rerank_config"),
    "selected_not_used": (
        "rag_not_grounded", "medical_rag", "rag_grounding", "grounding_rule"
    ),
    "selected_misinterpreted": (
        "rag_misinterpreted", "medical_rag", "rag_interpretation", "grounding_rule"
    ),
    "citation_mismatch": (
        "citation_mismatch", "medical_rag", "citation_binding", "citation_binding"
    ),
}

SUPPORTED_CAUSE_CODES = frozenset(_CAUSE_CLASSIFICATION)

_OWNER_COMPONENT = {
    "agent_prompt": ("prompt_hook", "static_prompt", "prompt_rule"),
    "prompt_static": ("prompt_hook", "static_prompt", "prompt_rule"),
    "prompt_hook": ("prompt_hook", "dynamic_hook", "hook_rule"),
    "expert_pack": ("prompt_hook", "expert_pack", "expert_pack"),
    "context_tool": ("context_memory", "context_usage", "context_injection"),
    "context_profile": ("context_memory", "structured_profile", "context_injection"),
    "context_medical_record": ("context_memory", "medical_record", "context_injection"),
    "context_timeline": ("context_memory", "timeline", "context_injection"),
    "context_chat_history": ("context_memory", "chat_history", "context_injection"),
    "memory_pipeline": ("context_memory", "memory_write", "memory_pipeline"),
    "orchestration": ("dialogue_tool_orchestration", "intent_routing", "dialogue_policy"),
    "feature_gate": ("dialogue_tool_orchestration", "feature_gate", "feature_gate"),
    "tool_registry": ("dialogue_tool_orchestration", "tool_registry", "tool_schema"),
    "tool_executor": ("dialogue_tool_orchestration", "tool_executor", "tool_executor"),
    "rag_corpus": ("medical_rag", "rag_corpus", "rag_corpus"),
    "retriever": ("medical_rag", "rag_retrieval", "retrieval_config"),
    "threshold": ("medical_rag", "rag_threshold", "threshold_config"),
    "reranker": ("medical_rag", "rag_rerank", "rerank_config"),
    "clinical_reasoning": ("clinical_reasoning", "clinical_synthesis", "clinical_reasoning"),
    "generator": ("response_delivery", "content_composition", "response_composition"),
    "safety_policy": ("medical_safety", "safety_policy", "safety_rule"),
    "response_protocol": ("response_delivery", "output_protocol", "response_protocol"),
    "delivery_ui": ("response_delivery", "delivery_ui", "delivery_ui"),
    "model_provider": ("model_runtime_observability", "model_provider", "runtime_resilience"),
    "runtime": ("model_runtime_observability", "partial_output", "runtime_resilience"),
    "observability": ("model_runtime_observability", "observability_evidence", "observability"),
}


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def normalize_optimization_classification(
    deduction: dict[str, Any], evaluation_issue_category: str = "none"
) -> dict[str, str]:
    """返回完整且稳定的优化分类，旧结果缺字段时也能确定性补齐。"""
    validation = str(deduction.get("deduction_validation") or "insufficient_evidence")
    cause = _record(deduction.get("primary_cause"))
    code = str(cause.get("code") or "insufficient_evidence").lower()
    owner = str(cause.get("owner") or "unknown").lower()
    supplied = _record(deduction.get("optimization_classification"))

    if evaluation_issue_category not in {"none", "missing_rag_reference", "evidence_gap"}:
        component = "benchmark" if evaluation_issue_category in {
            "benchmark_criteria_conflict", "annotation_rag_conflict"
        } else "judge"
        action_type = "evaluation_rule" if component == "benchmark" else "judge_logic"
        return {
            "domain": "evaluation_system",
            "component": component,
            "failure_mode": evaluation_issue_category,
            "action_type": action_type,
            "evidence_status": "sufficient",
            "coverage_status": "mapped",
        }

    if evaluation_issue_category == "missing_rag_reference":
        code = "missing_rag_reference"

    # RAG 阶段诊断比模型给出的泛化回答分类更接近因果链的最早失败节点。
    # 只有结构化诊断明确指出失败阶段时才纠偏；healthy/unknown/not_needed
    # 不会覆盖 primary_cause，避免仅凭“检索结果里出现过”就武断归责 RAG。
    rag_diagnosis = _record(deduction.get("rag_diagnosis"))
    diagnosis = str(rag_diagnosis.get("diagnosis") or "").lower()
    rag_fallback = _RAG_DIAGNOSIS_CLASSIFICATION.get(diagnosis)
    if not rag_fallback:
        information_stage = str(
            rag_diagnosis.get("relevant_information_stage") or ""
        ).lower()
        answer_usage = str(rag_diagnosis.get("answer_usage") or "").lower()
        if information_stage == "selected" and answer_usage == "not_used":
            rag_fallback = _RAG_DIAGNOSIS_CLASSIFICATION["selected_not_used"]
        elif information_stage == "selected" and answer_usage in {
            "misinterpreted", "unsupported_claim"
        }:
            rag_fallback = _RAG_DIAGNOSIS_CLASSIFICATION["selected_misinterpreted"]
    if evaluation_issue_category == "none" and rag_fallback:
        code, rag_domain, rag_component, rag_action = rag_fallback
        supplied = {
            **supplied,
            "domain": rag_domain,
            "component": rag_component,
            "action_type": rag_action,
        }

    if rag_fallback and evaluation_issue_category == "none":
        fallback = rag_fallback[1:]
        coverage_status = "mapped"
    elif code in _CAUSE_CLASSIFICATION:
        fallback = _CAUSE_CLASSIFICATION[code]
        coverage_status = "mapped"
    elif owner in _OWNER_COMPONENT:
        fallback = _OWNER_COMPONENT[owner]
        coverage_status = "owner_fallback"
    else:
        fallback = (
            "model_runtime_observability", "taxonomy_gap", "observability"
        )
        coverage_status = "unmapped"
    domain = str(supplied.get("domain") or "")
    component = str(supplied.get("component") or "")
    action_type = str(supplied.get("action_type") or "")
    # 允许模型在正确一级领域内给出更精确的代码组件，但不允许跨领域漂移。
    if domain not in DOMAIN_LABELS or domain != fallback[0]:
        domain = fallback[0]
    if component not in DOMAIN_COMPONENTS.get(domain, set()):
        component = fallback[1]
    if action_type not in DOMAIN_ACTION_TYPES.get(domain, set()):
        action_type = fallback[2]
    evidence_status = (
        "insufficient"
        if validation == "insufficient_evidence" or coverage_status == "unmapped"
        else "sufficient"
    )
    if validation == "supported" and str(supplied.get("evidence_status")) == "partial":
        evidence_status = "partial"
    return {
        "domain": domain,
        "component": component,
        "failure_mode": code,
        "action_type": action_type,
        "evidence_status": evidence_status,
        "coverage_status": coverage_status,
    }


def classification_labels(value: dict[str, Any]) -> dict[str, str]:
    """供 Open API/文档消费者直接展示中文标签。"""
    return {
        "domain_label": DOMAIN_LABELS.get(str(value.get("domain") or ""), "待确认领域"),
        "component_label": COMPONENT_LABELS.get(str(value.get("component") or ""), "待确认组件"),
        "action_type_label": ACTION_TYPE_LABELS.get(str(value.get("action_type") or ""), "待确认动作"),
    }
