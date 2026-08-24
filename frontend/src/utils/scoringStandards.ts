import { DIM_LABEL, EVALUATION_DIMENSIONS } from "../labels";
import type { ScoringStandard } from "../api/types";

export const SCORING_STANDARD_LABELS: Record<ScoringStandard, string> = {
  cx_eight_dimension: "Agent 评测八维",
  model_comparison: "模型对比八维",
};

export const MODEL_COMPARISON_DIMENSIONS = [
  "medical_knowledge_reasoning",
  "factuality_hallucination",
  "instruction_following",
  "context_personalization",
  "tool_use",
  "multimodal_understanding",
  "empathy_communication",
  "multi_turn_consistency",
] as const;

export const MODEL_COMPARISON_DIMENSION_LABELS: Record<
  (typeof MODEL_COMPARISON_DIMENSIONS)[number],
  string
> = {
  medical_knowledge_reasoning: "医学知识与临床推理",
  factuality_hallucination: "事实可靠性与幻觉控制",
  instruction_following: "指令遵循与产品边界",
  context_personalization: "上下文利用与个性化",
  tool_use: "工具选择与调用执行",
  multimodal_understanding: "图像与多模态理解",
  empathy_communication: "共情与患者沟通",
  multi_turn_consistency: "多轮一致性与状态保持",
};

export function normalizeScoringStandard(value?: string | null): ScoringStandard {
  return value === "model_comparison" ? "model_comparison" : "cx_eight_dimension";
}

export function scoringStandardLabel(value?: string | null): string {
  return SCORING_STANDARD_LABELS[normalizeScoringStandard(value)];
}

export function pairwiseDimensionKeys(value?: string | null): string[] {
  return normalizeScoringStandard(value) === "model_comparison"
    ? [...MODEL_COMPARISON_DIMENSIONS]
    : [...EVALUATION_DIMENSIONS];
}

export function pairwiseDimensionLabel(key: string): string {
  return MODEL_COMPARISON_DIMENSION_LABELS[
    key as keyof typeof MODEL_COMPARISON_DIMENSION_LABELS
  ] || DIM_LABEL[key] || key;
}
