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
    // 节点 UUID、消息序号和检索内部下标只用于系统回链，不应出现在业务描述中。
    .replace(
      /(?:终答生成节点|AI\s*助手调用(?:链)?节点|调用链节点)\s*[：:]?\s*(?:node:)?[a-z0-9][a-z0-9_-]{7,}/gi,
      "最终回答调用链",
    )
    .replace(/node:[a-z0-9_-]{8,}/gi, "AI 助手调用链")
    .replace(/rag:\d+:source:\d+(?::chunk:\d+)?/gi, "RAG 检索证据")
    .replace(/message:\d+/gi, "当前对话")
    .replace(/当前对话第\s*\d+\s*(?:条|轮)?/g, "当前对话")
    .replace(/对话消息\s*\d+/g, "当前对话")
    .replace(/score_health:\d+/gi, "判分健康检查")
    .replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi, "")
    .replace(/（当前对话）/g, "")
    .replace(/\(当前对话\)/g, "");

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
    .replace(/citation映射/gi, "引用编号映射")
    .replace(
      /调用链证据[：:]\s*(?:AI 助手调用链|最终回答调用链)\s*输出全文/g,
      "调用链证据：输出全文",
    )
    .replace(/(?:AI 助手调用链|最终回答调用链)\s*输出全文/g, "调用链证据：输出全文")
    .replace(/当前对话\s*(助手回答|用户提问|用户消息)/g, "当前对话中，$1")
    // 原始回链清单已由下方“证据范围”标签承载，不在描述里重复展示。
    .replace(/(?:^|\n|[；;])\s*来源[：:][^\n]*$/g, "")
    .replace(/[：:]\s*[；;,，]/g, "：")
    .replace(/\s{2,}/g, " ")
    .trim();
}

export function humanizeEvidenceRef(value: string, analyses: AttributionDeductionAnalysis[]) {
  const ragChunk = value.match(/^rag:(\d+):source:(\d+)(?::chunk:(\d+))?$/);
  if (ragChunk) {
    return "RAG 检索证据";
  }
  const message = value.match(/^message:(\d+)$/);
  if (message) return "当前对话";
  const caseContext = value.match(
    /^case:(user_profile|medical_record|timeline|history|definition)(?::(.+))?$/
  );
  if (caseContext) {
    const labels: Record<string, string> = {
      user_profile: "用户档案",
      medical_record: "病历与报告",
      timeline: "Timeline 长期事实",
      history: "历史事实",
      definition: "Case 定义",
    };
    return labels[caseContext[1]] || "用例上下文";
  }
  const node = value.match(/^node:(.+)$/);
  if (node) return "AI 助手调用链";
  if (value === "run:config") return "评测运行配置";
  if (value === "trace:agent_chain") return "AI 助手调用链摘要";
  if (value === "trace:observability") return "RAG 与链路可观测性摘要";
  const scoreHealth = value.match(/^score_health:(\d+)$/);
  if (scoreHealth) return "判分健康检查";
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
  optimization_classification?: AttributionOptimizationClassification;
  rag_diagnosis?: {
    diagnosis?: string;
    query_quality?: string;
    relevant_information_stage?: string;
    answer_usage?: string;
  };
  recommendations?: AttributionRecommendation[];
};

const CURRENT_CATEGORY_KEYS: Record<string, string> = {
  "RAG 优化": "rag",
  "Agent 工程链路": "engineering",
  "Agent 决策与推理策略": "reasoning",
  "提示词与回答生成策略": "prompt",
  "知识与规则内化": "knowledge",
  "输出校验与安全守卫": "safety",
};

type DocumentCategoryKey = "rag" | "engineering" | "reasoning" | "prompt" | "knowledge" | "safety" | "unclassified";

/** 直接使用归因结果中的现行分类，不再从旧 cause/owner/domain 映射。 */
export function cxAgentSuggestionCategory(
  source: CxAgentSuggestionSource,
): CxAgentSuggestionCategory {
  const primaryLabel = String(source.optimization_classification?.category_primary || "").trim();
  const secondaryLabel = String(source.optimization_classification?.category_secondary || "").trim();
  const primaryKey = CURRENT_CATEGORY_KEYS[primaryLabel] || "unclassified";
  if (!primaryLabel || !secondaryLabel || primaryKey === "unclassified") {
    return {
      key: "unclassified:待确认",
      label: "未分类 / 待确认",
      primaryLabel: "未分类",
      secondaryLabel: "待确认",
    };
  }
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
