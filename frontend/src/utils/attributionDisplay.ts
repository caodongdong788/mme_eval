import type {
  AttributionDeductionAnalysis,
  AttributionOptimizationClassification,
  AttributionRecommendation,
} from "../api";
import { DIM_LABEL } from "../labels";

const TECHNICAL_TERMS: Array<[RegExp, string]> = [
  [/candidate_membership_available=false/gi, "缺少候选文献归属数据"],
  [/candidate_membership_available=true/gi, "候选文献归属数据完整"],
  [/candidate_membership/gi, "候选文献归属数据"],
  [/medical_literature_search/gi, "医学文献检索工具"],
  [/initial_state\.user_profile/gi, "用户预置档案"],
  [/system[ _]prompt/gi, "系统提示词"],
  [/system[ _]message/gi, "系统上下文消息"],
  [/rag_audits/gi, "RAG 审计记录"],
  [/rag[ _]source/gi, "RAG 文献来源"],
  [/AI\s*助手提示词/g, "提示词优化"],
  [/agent_prompt/gi, "提示词优化"],
  [/\bJudge\b/gi, "判分模型"],
  [/\bAgent\b/gi, "AI 助手"],
  [/\bbenchmark\b/gi, "评测判据"],
  [/\bguideline\b/gi, "指南扣分项"],
  [/\bgenerator\b/gi, "回答生成环节"],
  [/\borchestration\b/gi, "对话流程编排"],
  [/\bselected\b/gi, "最终选中文献"],
  [/\bunknown\b/gi, "无法判断"],
  [/\bquery\b/gi, "检索问题"],
  [/\bchunk\b/gi, "文献片段"],
  [/\bsource\b/gi, "来源"],
  [/\bcase\b/gi, "用例"],
  [/\brun\b/gi, "评测任务"],
];

const PRIORITY_LABELS: Record<string, string> = {
  P0: "最高优先级",
  P1: "较高优先级",
  P2: "一般优先级",
};

const QUERY_QUALITY_LABELS: Record<string, string> = {
  good: "查询准确",
  incomplete: "查询不完整",
  wrong: "查询错误",
  unknown: "无法判断",
};

const INFORMATION_STAGE_LABELS: Record<string, string> = {
  all: "原始召回",
  qualified: "阈值过滤后",
  candidate: "候选文献",
  selected: "最终选中文献",
  not_found: "未召回相关信息",
  unknown: "无法判断",
};

const ANSWER_USAGE_LABELS: Record<string, string> = {
  used: "已正确使用",
  not_used: "召回但未使用",
  misinterpreted: "使用时理解错误",
  unsupported_claim: "回答缺少证据支持",
  unknown: "无法判断",
};

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function dimensionKey(value?: string) {
  return String(value || "").replace(/^dimension\./, "");
}

export function dimensionDisplayName(value?: string) {
  const key = dimensionKey(value);
  return DIM_LABEL[key] || "未关联维度";
}

function guidelineNumber(value: string) {
  const matched = value.match(/(?:^|\.)g(\d+)/i);
  return matched?.[1];
}

export function attributionDeductionLabel(
  item: Pick<AttributionDeductionAnalysis, "deduction_id" | "dimension">,
) {
  if (item.deduction_id.startsWith("dimension.")) {
    return dimensionDisplayName(item.deduction_id);
  }
  if (item.deduction_id.startsWith("guideline.")) {
    const number = guidelineNumber(item.deduction_id);
    return number
      ? `指南扣分项 ${number}（${dimensionDisplayName(item.dimension)}）`
      : `指南扣分项（${dimensionDisplayName(item.dimension)}）`;
  }
  if (item.deduction_id.startsWith("assertion.")) return "规则校验项";
  return dimensionDisplayName(item.dimension);
}

export function humanizeAttributionText(
  value?: string,
  analyses: AttributionDeductionAnalysis[] = [],
) {
  let output = String(value || "").trim();
  if (!output) return "—";

  output = output
    .replace(/rag:(\d+):source:(\d+):chunk:(\d+)/gi, "第 $1 次 RAG 检索 · 文献 $2 · 片段 $3")
    .replace(/rag:(\d+):source:(\d+)/gi, "第 $1 次 RAG 检索 · 文献 $2")
    .replace(/message:(\d+)/gi, "对话消息 $1");

  analyses.forEach((item) => {
    output = output.replace(
      new RegExp(escapeRegExp(item.deduction_id), "gi"),
      attributionDeductionLabel(item),
    );
  });
  Object.entries(DIM_LABEL).forEach(([key, label]) => {
    output = output.replace(new RegExp(`dimension\\.${escapeRegExp(key)}`, "gi"), label);
    output = output.replace(new RegExp(`\\b${escapeRegExp(key)}\\b`, "gi"), label);
  });

  output = output.replace(/guideline\.g(\d+)(?:_[a-z_]+)?/gi, (_, number: string) => `指南扣分项 ${number}`);

  const guidelineLabels = new Map<string, string>();
  analyses.forEach((item) => {
    const number = guidelineNumber(item.deduction_id);
    if (number) guidelineLabels.set(`g${number}`.toLowerCase(), attributionDeductionLabel(item));
  });
  output = output.replace(/\bg\d{1,3}\b/gi, (token) => {
    const known = guidelineLabels.get(token.toLowerCase());
    return known || `指南扣分项 ${token.slice(1)}`;
  });

  TECHNICAL_TERMS.forEach(([pattern, label]) => {
    output = output.replace(pattern, label);
  });
  return output
    .replace(/评测判据判据/g, "评测判据")
    .replace(/system消息/gi, "系统上下文消息")
    .replace(/agent_chain/gi, "AI 助手调用链")
    .replace(/dimension_criteria/gi, "八维评测要求")
    .replace(/citation映射/gi, "引用编号映射");
}

export function humanizeEvidenceRef(value: string, analyses: AttributionDeductionAnalysis[]) {
  const ragChunk = value.match(/^rag:(\d+):source:(\d+)(?::chunk:(\d+))?$/);
  if (ragChunk) {
    return `第 ${ragChunk[1]} 次 RAG 检索 · 文献 ${ragChunk[2]}${ragChunk[3] ? ` · 片段 ${ragChunk[3]}` : ""}`;
  }
  const message = value.match(/^message:(\d+)$/);
  if (message) return `对话消息 ${message[1]}`;
  return humanizeAttributionText(value, analyses);
}

export function priorityDisplayName(value?: string) {
  return PRIORITY_LABELS[String(value || "").toUpperCase()] || "优化建议";
}

export type CxAgentSuggestionCategory = {
  key: string;
  label: string;
  primaryLabel: string;
  secondaryLabel: string;
};

type CxAgentSuggestionSource = {
  owner?: string;
  evaluation_issue_category?: string;
  cause_code?: string;
  rag_optimization_category?: string;
  optimization_classification?: AttributionOptimizationClassification;
  rag_diagnosis?: {
    diagnosis?: string;
    query_quality?: string;
    answer_usage?: string;
  };
  recommendations?: AttributionRecommendation[];
};

/**
 * 归因展示必须与《CX-Agent 自动化评测归因与优化方法》中的一级、二级
 * 分类保持一致。内部模块名用于定位代码，不直接暴露给使用者。
 */
const DOCUMENT_CATEGORY_LABELS = {
  rag: "RAG 优化",
  engineering: "Agent 工程链路",
  reasoning: "Agent 决策与推理策略",
  prompt: "提示词与回答生成策略",
  knowledge: "知识与规则内化",
  safety: "输出校验与安全守卫",
} as const;

type DocumentCategoryKey = keyof typeof DOCUMENT_CATEGORY_LABELS;

type DocumentCategory = [DocumentCategoryKey, string];

const RAG_DOCUMENT_COMPONENTS: Record<string, string> = {
  rag_trigger: "未触发检索",
  rag_service: "调用失败",
  rag_query: "Query 不完整或意图识别偏差",
  rag_corpus: "召回覆盖不足",
  rag_retrieval: "召回覆盖不足",
  rag_threshold: "召回覆盖不足",
  rag_candidate: "排序或重排不当",
  rag_rerank: "排序或重排不当",
  rag_grounding: "已召回但未使用",
  rag_interpretation: "证据误读",
  citation_binding: "缺少 RAG 引用",
};

function documentedSuggestionCategory(domain: string, component: string): DocumentCategory {
  if (domain === "medical_rag") {
    return ["rag", RAG_DOCUMENT_COMPONENTS[component] || "召回覆盖不足"];
  }
  if (domain === "context_memory") {
    if (["timeline", "structured_profile", "medical_record", "chat_history", "saved_content"].includes(component)) {
      return ["engineering", "Timeline 或用户事实未注入"];
    }
    if (component === "context_usage") return ["engineering", "上下文已注入但未使用"];
    return ["engineering", "多轮状态丢失"];
  }
  if (domain === "dialogue_tool_orchestration") {
    if (component === "tool_registry") return ["engineering", "工具未调用"];
    if (component === "tool_selection") return ["engineering", "工具选择错误"];
    if (component === "tool_arguments") return ["engineering", "工具参数错误"];
    if (["tool_policy", "tool_executor"].includes(component)) return ["engineering", "工具执行失败"];
    if (component === "clarification") return ["reasoning", "未优先追问关键问题"];
    return ["engineering", "流程路由错误"];
  }
  if (domain === "prompt_hook") {
    if (component === "dynamic_hook") return ["prompt", "未说清红旗信号"];
    if (component === "expert_pack") return ["prompt", "缺少适用条件或解释"];
    return ["prompt", "未说明适用边界"];
  }
  if (domain === "clinical_reasoning") {
    if (component === "risk_benefit" || component === "clinical_fact_extraction") {
      return ["reasoning", "风险识别不足"];
    }
    if (component === "contraindication") return ["reasoning", "禁忌或相互作用判断不足"];
    return ["reasoning", "错误选择行动路径"];
  }
  if (domain === "response_delivery") {
    if (component === "response_style") return ["prompt", "缺少共情与确认"];
    if (component === "content_composition") return ["prompt", "行动步骤不清晰"];
    if (component === "output_protocol") return ["safety", "未执行终答前检查"];
    return ["prompt", "缺少适用条件或解释"];
  }
  if (domain === "medical_safety") return ["safety", "放出不安全建议"];
  if (domain === "model_runtime_observability") return ["engineering", "工具执行失败"];
  if (domain === "evaluation_system") return ["engineering", "流程路由错误"];
  return ["engineering", "流程路由错误"];
}

const CAUSE_CLASSIFICATION: Record<string, [string, string]> = {
  safety_policy_error: ["medical_safety", "safety_policy"],
  prompt_rule_error: ["prompt_hook", "static_prompt"],
  hook_rule_error: ["prompt_hook", "dynamic_hook"],
  expert_pack_error: ["prompt_hook", "expert_pack"],
  context_not_fetched: ["context_memory", "structured_profile"],
  context_not_used: ["context_memory", "context_usage"],
  context_subject_error: ["context_memory", "consult_subject"],
  context_stale_or_conflict: ["context_memory", "context_conflict"],
  memory_write_error: ["context_memory", "memory_write"],
  intent_routing_error: ["dialogue_tool_orchestration", "intent_routing"],
  clarification_strategy_error: ["dialogue_tool_orchestration", "clarification"],
  feature_gate_error: ["dialogue_tool_orchestration", "feature_gate"],
  tool_not_available: ["dialogue_tool_orchestration", "tool_registry"],
  tool_not_called: ["dialogue_tool_orchestration", "tool_selection"],
  tool_selection_error: ["dialogue_tool_orchestration", "tool_selection"],
  tool_argument_error: ["dialogue_tool_orchestration", "tool_arguments"],
  tool_blocked: ["dialogue_tool_orchestration", "tool_policy"],
  tool_execution_failed: ["dialogue_tool_orchestration", "tool_executor"],
  tool_timeout: ["dialogue_tool_orchestration", "tool_executor"],
  proactive_or_undercurrent_error: ["dialogue_tool_orchestration", "proactive_undercurrent"],
  rag_not_needed: ["medical_rag", "rag_trigger"],
  rag_not_called: ["medical_rag", "rag_trigger"],
  rag_call_failed: ["medical_rag", "rag_service"],
  rag_query_error: ["medical_rag", "rag_query"],
  rag_corpus_gap: ["medical_rag", "rag_corpus"],
  rag_recall_error: ["medical_rag", "rag_retrieval"],
  rag_threshold_error: ["medical_rag", "rag_threshold"],
  rag_candidate_or_rerank_error: ["medical_rag", "rag_candidate"],
  rag_rerank_error: ["medical_rag", "rag_rerank"],
  rag_not_grounded: ["medical_rag", "rag_grounding"],
  rag_misinterpreted: ["medical_rag", "rag_interpretation"],
  citation_mismatch: ["medical_rag", "citation_binding"],
  missing_rag_reference: ["medical_rag", "citation_binding"],
  reasoning_error: ["clinical_reasoning", "clinical_synthesis"],
  clinical_fact_extraction_error: ["clinical_reasoning", "clinical_fact_extraction"],
  temporal_reasoning_error: ["clinical_reasoning", "temporal_reasoning"],
  risk_benefit_error: ["clinical_reasoning", "risk_benefit"],
  contraindication_error: ["clinical_reasoning", "contraindication"],
  response_composition_error: ["response_delivery", "content_composition"],
  response_incomplete: ["response_delivery", "response_completeness"],
  response_style_error: ["response_delivery", "response_style"],
  output_protocol_error: ["response_delivery", "output_protocol"],
  a2ui_binding_error: ["response_delivery", "a2ui_binding"],
  delivery_render_error: ["response_delivery", "delivery_ui"],
  model_api_error: ["model_runtime_observability", "model_provider"],
  model_timeout: ["model_runtime_observability", "model_timeout"],
  model_partial_output: ["model_runtime_observability", "partial_output"],
  context_window_error: ["model_runtime_observability", "context_window"],
  compaction_error: ["model_runtime_observability", "compaction"],
  tool_result_truncated: ["model_runtime_observability", "tool_result_budget"],
  observability_gap: ["model_runtime_observability", "observability_evidence"],
  insufficient_evidence: ["model_runtime_observability", "observability_evidence"],
};

const RAG_DIAGNOSIS_CLASSIFICATION: Record<string, [string, string]> = {
  not_called: ["medical_rag", "rag_trigger"],
  failed: ["medical_rag", "rag_service"],
  query_error: ["medical_rag", "rag_query"],
  corpus_gap: ["medical_rag", "rag_corpus"],
  recall_error: ["medical_rag", "rag_retrieval"],
  threshold_error: ["medical_rag", "rag_threshold"],
  candidate_or_rerank_error: ["medical_rag", "rag_candidate"],
  rerank_error: ["medical_rag", "rag_rerank"],
  selected_not_used: ["medical_rag", "rag_grounding"],
  selected_misinterpreted: ["medical_rag", "rag_interpretation"],
  citation_mismatch: ["medical_rag", "citation_binding"],
};

function suggestionClassification(source: CxAgentSuggestionSource): [string, string] {
  const structured = source.optimization_classification;
  if (structured?.domain && structured?.component) {
    return [structured.domain, structured.component];
  }
  if (source.evaluation_issue_category === "missing_rag_reference") {
    return CAUSE_CLASSIFICATION.missing_rag_reference;
  }
  const causeCode = String(source.cause_code || source.rag_optimization_category || "").toLowerCase();
  if (CAUSE_CLASSIFICATION[causeCode]) return CAUSE_CLASSIFICATION[causeCode];
  const diagnosis = String(source.rag_diagnosis?.diagnosis || "").toLowerCase();
  if (RAG_DIAGNOSIS_CLASSIFICATION[diagnosis]) return RAG_DIAGNOSIS_CLASSIFICATION[diagnosis];
  const queryQuality = String(source.rag_diagnosis?.query_quality || "").toLowerCase();
  if (["incomplete", "wrong"].includes(queryQuality)) return ["medical_rag", "rag_query"];
  const answerUsage = String(source.rag_diagnosis?.answer_usage || "").toLowerCase();
  if (answerUsage === "not_used") return ["medical_rag", "rag_grounding"];
  if (["misinterpreted", "unsupported_claim"].includes(answerUsage)) {
    return ["medical_rag", "rag_interpretation"];
  }
  const owner = String(source.owner || "").toLowerCase();
  const ownerFallback: Record<string, [string, string]> = {
    safety_policy: ["medical_safety", "safety_policy"],
    agent_prompt: ["prompt_hook", "static_prompt"],
    prompt_static: ["prompt_hook", "static_prompt"],
    prompt_hook: ["prompt_hook", "dynamic_hook"],
    expert_pack: ["prompt_hook", "expert_pack"],
    context_tool: ["context_memory", "context_usage"],
    context_profile: ["context_memory", "structured_profile"],
    context_medical_record: ["context_memory", "medical_record"],
    context_timeline: ["context_memory", "timeline"],
    context_chat_history: ["context_memory", "chat_history"],
    memory_pipeline: ["context_memory", "memory_write"],
    orchestration: ["dialogue_tool_orchestration", "intent_routing"],
    feature_gate: ["dialogue_tool_orchestration", "feature_gate"],
    tool_registry: ["dialogue_tool_orchestration", "tool_registry"],
    tool_executor: ["dialogue_tool_orchestration", "tool_executor"],
    rag_corpus: ["medical_rag", "rag_corpus"],
    retriever: ["medical_rag", "rag_retrieval"],
    threshold: ["medical_rag", "rag_threshold"],
    reranker: ["medical_rag", "rag_rerank"],
    clinical_reasoning: ["clinical_reasoning", "clinical_synthesis"],
    generator: ["response_delivery", "content_composition"],
    response_protocol: ["response_delivery", "output_protocol"],
    delivery_ui: ["response_delivery", "delivery_ui"],
    model_provider: ["model_runtime_observability", "model_provider"],
    runtime: ["model_runtime_observability", "partial_output"],
    observability: ["model_runtime_observability", "observability_evidence"],
  };
  return ownerFallback[owner] || ["model_runtime_observability", "observability_evidence"];
}

/**
 * 把模型给出的根因和建议转成稳定、面向业务的优化分类。
 * 任务汇总和单 Case 使用同一规则，避免同一个问题在两个页面落到不同类别。
 */
export function cxAgentSuggestionCategory(
  source: CxAgentSuggestionSource,
): CxAgentSuggestionCategory {
  const [domain, component] = suggestionClassification(source);
  const [primaryKey, secondaryLabel] = documentedSuggestionCategory(domain, component);
  const primaryLabel = DOCUMENT_CATEGORY_LABELS[primaryKey];
  return {
    key: `${primaryKey}:${secondaryLabel}`,
    label: `${primaryLabel} / ${secondaryLabel}`,
    primaryLabel,
    secondaryLabel,
  };
}

export function cxAgentSuggestionCategoryOrder(key: string) {
  const primary = key.split(":", 1)[0];
  const order: DocumentCategoryKey[] = [
    "rag",
    "engineering",
    "reasoning",
    "prompt",
    "knowledge",
    "safety",
  ];
  const index = order.indexOf(primary as DocumentCategoryKey);
  return index === -1 ? order.length : index;
}

export function queryQualityDisplayName(value?: string) {
  return QUERY_QUALITY_LABELS[String(value || "")] || "无法判断";
}

export function informationStageDisplayName(value?: string) {
  return INFORMATION_STAGE_LABELS[String(value || "")] || "无法判断";
}

export function answerUsageDisplayName(value?: string) {
  return ANSWER_USAGE_LABELS[String(value || "")] || "无法判断";
}
