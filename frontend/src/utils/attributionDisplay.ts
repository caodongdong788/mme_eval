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

const CX_AGENT_SUGGESTION_CATEGORY_ORDER = [
  "medical_safety",
  "prompt_hook",
  "context_memory",
  "dialogue_tool_orchestration",
  "medical_rag",
  "clinical_reasoning",
  "response_delivery",
  "model_runtime_observability",
  "evaluation_system",
];

const CX_AGENT_DOMAIN_LABELS: Record<string, string> = {
  medical_safety: "医学安全与策略",
  prompt_hook: "Prompt、Hook 与专家配置",
  context_memory: "用户上下文与长期记忆",
  dialogue_tool_orchestration: "对话与工具编排",
  medical_rag: "医学文献 RAG",
  clinical_reasoning: "临床推理与方案合成",
  response_delivery: "回答生成与交付协议",
  model_runtime_observability: "模型运行时与可观测性",
  evaluation_system: "评测系统复核",
};

const CX_AGENT_COMPONENT_LABELS: Record<string, string> = {
  safety_policy: "医学安全策略",
  static_prompt: "静态 Prompt",
  dynamic_hook: "动态 Hook / Reminder",
  expert_pack: "专家配置",
  structured_profile: "用户结构化档案",
  medical_record: "病历与医学指标",
  timeline: "Timeline 长期事实",
  chat_history: "历史对话",
  saved_content: "病例夹与已保存资料",
  consult_subject: "咨询对象归属",
  context_usage: "上下文利用",
  context_conflict: "上下文新旧冲突",
  memory_write: "长期记忆写入与维护",
  intent_routing: "意图与流程路由",
  clarification: "追问与澄清策略",
  feature_gate: "能力开关",
  tool_registry: "工具注册与可见性",
  tool_selection: "工具选择",
  tool_arguments: "工具参数",
  tool_policy: "工具调用策略",
  tool_executor: "工具执行",
  proactive_undercurrent: "主动服务与暗流 Agent",
  rag_trigger: "RAG 触发决策",
  rag_service: "RAG 服务调用",
  rag_query: "检索问题改写",
  rag_corpus: "医学知识库",
  rag_retrieval: "原始召回",
  rag_threshold: "阈值与过滤",
  rag_candidate: "候选文献生成（证据不足以定位重排）",
  rag_rerank: "候选重排",
  rag_grounding: "召回证据利用",
  rag_interpretation: "医学证据理解",
  citation_binding: "引用绑定",
  clinical_fact_extraction: "临床事实提取",
  temporal_reasoning: "时间线推理",
  risk_benefit: "风险收益权衡",
  contraindication: "禁忌与相互作用",
  clinical_synthesis: "临床方案合成",
  content_composition: "回答内容组织",
  response_completeness: "回答完整性",
  response_style: "表达与沟通风格",
  output_protocol: "终答输出协议",
  a2ui_binding: "A2UI 与资源绑定",
  delivery_ui: "SSE 与前端交付",
  model_provider: "模型供应商调用",
  model_timeout: "模型流式超时",
  partial_output: "模型部分或空输出",
  context_window: "上下文窗口",
  compaction: "上下文压缩",
  tool_result_budget: "工具结果预算与截断",
  observability_evidence: "调用链与证据采集",
  taxonomy_gap: "归因分类待补充",
  benchmark: "Benchmark 判据",
  judge: "判分模型",
};

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
  const domainLabel = CX_AGENT_DOMAIN_LABELS[domain] || "待确认优化领域";
  const componentLabel = CX_AGENT_COMPONENT_LABELS[component] || "待确认组件";
  return { key: `${domain}:${component}`, label: `${domainLabel} · ${componentLabel}` };
}

export function cxAgentSuggestionCategoryOrder(key: string) {
  const domain = key.split(":", 1)[0];
  const index = CX_AGENT_SUGGESTION_CATEGORY_ORDER.indexOf(domain);
  return index === -1 ? CX_AGENT_SUGGESTION_CATEGORY_ORDER.length : index;
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
