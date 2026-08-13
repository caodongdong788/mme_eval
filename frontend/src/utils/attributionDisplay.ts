import type { AttributionDeductionAnalysis } from "../api";
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
  [/agent_prompt/gi, "AI 助手提示词"],
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
  return DIM_LABEL[key] || "综合评分维度";
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
  return output;
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

export function queryQualityDisplayName(value?: string) {
  return QUERY_QUALITY_LABELS[String(value || "")] || "无法判断";
}

export function informationStageDisplayName(value?: string) {
  return INFORMATION_STAGE_LABELS[String(value || "")] || "无法判断";
}

export function answerUsageDisplayName(value?: string) {
  return ANSWER_USAGE_LABELS[String(value || "")] || "无法判断";
}
