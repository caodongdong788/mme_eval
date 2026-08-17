import type {
  AttributionDeductionAnalysis,
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
  rag_diagnosis?: {
    diagnosis?: string;
    query_quality?: string;
    answer_usage?: string;
  };
  recommendations?: AttributionRecommendation[];
};

const CX_AGENT_SUGGESTION_CATEGORY_ORDER = [
  "safety_policy",
  "prompt",
  "rag_not_called",
  "rag_query_error",
  "rag_recall_error",
  "rag_threshold_error",
  "rag_rerank_error",
  "rag_not_grounded",
  "rag_misinterpreted",
  "rag_corpus_gap",
  "rag_missing_reference",
  "rag_other",
  "context",
  "orchestration",
  "generation",
  "other",
];

const CX_AGENT_SUGGESTION_CATEGORY_LABELS: Record<string, string> = {
  safety_policy: "安全策略优化",
  prompt: "提示词优化",
  rag_not_called: "未触发 RAG",
  rag_query_error: "检索词不完整或错误",
  rag_recall_error: "召回不足",
  rag_threshold_error: "阈值/过滤过严",
  rag_rerank_error: "重排选择错误",
  rag_not_grounded: "召回后未引用",
  rag_misinterpreted: "证据理解错误",
  rag_corpus_gap: "知识库缺失或过期",
  rag_missing_reference: "缺少 RAG 引用",
  rag_other: "其他 RAG 优化",
  context: "用户信息读取优化",
  orchestration: "对话流程优化",
  generation: "回答生成优化",
  other: "其他回答优化",
};

/**
 * 把模型给出的根因和建议转成稳定、面向业务的优化分类。
 * 任务汇总和单 Case 使用同一规则，避免同一个问题在两个页面落到不同类别。
 */
export function cxAgentSuggestionCategory(
  source: CxAgentSuggestionSource,
): CxAgentSuggestionCategory {
  const owner = String(source.owner || "").toLowerCase();
  const causeCode = String(source.cause_code || "").toLowerCase();
  const ragDiagnosis = source.rag_diagnosis || {};
  const diagnosis = String(ragDiagnosis.diagnosis || "").toLowerCase();
  const queryQuality = String(ragDiagnosis.query_quality || "").toLowerCase();
  const answerUsage = String(ragDiagnosis.answer_usage || "").toLowerCase();
  const text = (source.recommendations || [])
    .map((item) => `${item.target || ""} ${item.action || ""}`)
    .join(" ")
    .toLowerCase();
  const has = (pattern: RegExp) => pattern.test(`${owner} ${text}`);

  const ragCategory = String(source.rag_optimization_category || "").toLowerCase();
  const resolvedRagCategory = (() => {
    if (ragCategory) return ragCategory;
    if (source.evaluation_issue_category === "missing_rag_reference") return "missing_rag_reference";
    if (["rag_not_called", "rag_call_failed"].includes(causeCode) || ["not_called", "failed"].includes(diagnosis)) return "rag_not_called";
    if (causeCode === "rag_query_error" || diagnosis === "query_error" || ["incomplete", "wrong"].includes(queryQuality)) return "rag_query_error";
    if (causeCode === "rag_recall_error" || diagnosis === "recall_error") return "rag_recall_error";
    if (causeCode === "rag_threshold_error" || diagnosis === "threshold_error") return "rag_threshold_error";
    if (["rag_candidate_or_rerank_error", "rag_rerank_error"].includes(causeCode) || ["candidate_or_rerank_error", "rerank_error"].includes(diagnosis)) return "rag_rerank_error";
    if (causeCode === "rag_not_grounded" || diagnosis === "selected_not_used" || answerUsage === "not_used") return "rag_not_grounded";
    if (causeCode === "rag_misinterpreted" || diagnosis === "selected_misinterpreted" || ["misinterpreted", "unsupported_claim"].includes(answerUsage)) return "rag_misinterpreted";
    if (causeCode === "rag_corpus_gap" || diagnosis === "corpus_gap") return "rag_corpus_gap";
    return "";
  })();

  if (resolvedRagCategory) {
    const key = resolvedRagCategory === "missing_rag_reference"
      ? "rag_missing_reference"
      : resolvedRagCategory === "rag_call_failed"
        ? "rag_not_called"
        : resolvedRagCategory;
    return { key, label: CX_AGENT_SUGGESTION_CATEGORY_LABELS[key] || CX_AGENT_SUGGESTION_CATEGORY_LABELS.rag_other };
  }
  if (has(/rag|知识库|文献|检索|召回|重排|引用|grounding/)) {
    return { key: "rag_other", label: CX_AGENT_SUGGESTION_CATEGORY_LABELS.rag_other };
  }
  if (has(/safety_policy|安全策略|安全门槛|红旗|风险拦截/)) {
    return {
      key: "safety_policy",
      label: CX_AGENT_SUGGESTION_CATEGORY_LABELS.safety_policy,
    };
  }
  if (has(/agent_prompt|prompt|提示词|系统提示/)) {
    return { key: "prompt", label: CX_AGENT_SUGGESTION_CATEGORY_LABELS.prompt };
  }
  if (has(/context_tool|上下文|用户档案|用户信息|画像/)) {
    return { key: "context", label: CX_AGENT_SUGGESTION_CATEGORY_LABELS.context };
  }
  if (has(/orchestration|流程编排|对话流程|追问策略|clarification/)) {
    return {
      key: "orchestration",
      label: CX_AGENT_SUGGESTION_CATEGORY_LABELS.orchestration,
    };
  }
  if (has(/generator|回答生成|生成阶段|回答策略/)) {
    return {
      key: "generation",
      label: CX_AGENT_SUGGESTION_CATEGORY_LABELS.generation,
    };
  }
  return { key: "other", label: CX_AGENT_SUGGESTION_CATEGORY_LABELS.other };
}

export function cxAgentSuggestionCategoryOrder(key: string) {
  const index = CX_AGENT_SUGGESTION_CATEGORY_ORDER.indexOf(key);
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
