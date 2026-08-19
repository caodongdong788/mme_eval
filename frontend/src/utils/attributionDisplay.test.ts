import { describe, expect, it } from "vitest";
import type { AttributionDeductionAnalysis } from "../api";
import {
  answerUsageDisplayName,
  attributionDeductionLabel,
  cxAgentSuggestionCategory,
  humanizeAttributionText,
  informationStageDisplayName,
  queryQualityDisplayName,
} from "./attributionDisplay";

function deduction(deductionId: string, dimension: string): AttributionDeductionAnalysis {
  return {
    deduction_id: deductionId,
    dimension,
    deduction_validation: "questionable",
    issue_type: "other",
    required_information: [],
    finding: "需要复核",
    causal_chain: [],
    primary_cause: { code: "judge_or_benchmark_issue", label: "判分依据需要复核", owner: "judge", confidence: 0.8 },
    contributing_causes: [],
    rag_diagnosis: { needed: true, called: true, query_quality: "good", relevant_information_stage: "selected", answer_usage: "used", finding: "链路正常" },
    recommendations: [],
  };
}

describe("attributionDisplay", () => {
  const analyses = [
    deduction("dimension.professional_accuracy", "professional_accuracy"),
    deduction("guideline.g02_medical_safety", "medical_safety"),
    deduction("guideline.g03_professional_accuracy", "professional_accuracy"),
  ];

  it("turns internal deduction ids into clear Chinese labels", () => {
    expect(attributionDeductionLabel(analyses[0])).toBe("专业准确性与边界");
    expect(attributionDeductionLabel(analyses[1])).toBe("指南扣分项 02（医学安全性）");
    expect(humanizeAttributionText("g02/g03判据与dimension.professional_accuracy冲突，Judge需复核", analyses))
      .toBe("指南扣分项 02（医学安全性）/指南扣分项 03（专业准确性与边界）判据与专业准确性与边界冲突，判分模型需复核");
    expect(humanizeAttributionText("initial_state.user_profile由system message提供，generator需要复核guideline.g05", analyses))
      .toBe("用户预置档案由系统上下文消息提供，回答生成环节需要复核指南扣分项 05");
    expect(humanizeAttributionText("rag:1:source:2:chunk:1与message:2是证据", analyses))
      .toBe("RAG 检索证据与当前对话是证据");
  });

  it("removes internal node ids and message indexes from business descriptions", () => {
    expect(humanizeAttributionText(
      "对话证据：当前对话第 2 条未追问；调用链证据：终答生成节点 node:50641f18-7b32-445e-bf00-66c4b7976418 输出全文无手术类型与麻醉方式追问；系统侧也未禁止该追问。\n来源：对话消息 2 AI 助手调用链节点：19d78d4c8260fbb0",
      analyses,
    )).toBe(
      "对话证据：当前对话未追问；调用链证据：输出全文无手术类型与麻醉方式追问；系统侧也未禁止该追问。",
    );
  });

  it("turns RAG diagnostic enums into user-facing language", () => {
    expect(queryQualityDisplayName("good")).toBe("查询准确");
    expect(informationStageDisplayName("selected")).toBe("最终选中文献");
    expect(answerUsageDisplayName("used")).toBe("已正确使用");
  });

  it("uses the business-facing prompt optimization label", () => {
    expect(humanizeAttributionText("AI 助手提示词与agent_prompt均需调整"))
      .toBe("提示词优化与提示词优化均需调整");
  });

  it("groups structured RAG diagnoses into actionable optimization directions", () => {
    expect(cxAgentSuggestionCategory({
      cause_code: "rag_not_called",
      optimization_classification: {
        category_primary: "RAG 优化",
        category_secondary: "未触发检索",
        domain: "medical_rag",
        component: "rag_trigger",
        failure_mode: "rag_not_called",
        action_type: "rag_trigger",
        evidence_status: "sufficient",
      },
    }).label).toBe("RAG 优化 / 未触发检索");
  });

  it("does not infer a display category from legacy cause or owner fields", () => {
    expect(cxAgentSuggestionCategory({ cause_code: "context_not_fetched" }).label)
      .toBe("未分类 / 待确认");
    expect(cxAgentSuggestionCategory({ owner: "agent_prompt" }).label)
      .toBe("未分类 / 待确认");
  });

  it("prefers validated structured classification over legacy owner fallbacks", () => {
    expect(cxAgentSuggestionCategory({
      owner: "generator",
      cause_code: "response_composition_error",
      optimization_classification: {
        category_primary: "Agent 决策与推理策略",
        category_secondary: "禁忌或相互作用判断不足",
        domain: "clinical_reasoning",
        component: "contraindication",
        failure_mode: "contraindication_error",
        action_type: "clinical_reasoning",
        evidence_status: "sufficient",
      },
    }).label).toBe("Agent 决策与推理策略 / 禁忌或相互作用判断不足");
  });

  it("keeps the model supplied current category instead of remapping RAG fields", () => {
    expect(cxAgentSuggestionCategory({
      cause_code: "response_composition_error",
      optimization_classification: {
        category_primary: "提示词与回答生成策略",
        category_secondary: "行动步骤不清晰",
        domain: "response_delivery",
        component: "content_composition",
        failure_mode: "response_composition_error",
        action_type: "response_composition",
        evidence_status: "sufficient",
      },
      rag_diagnosis: {
        diagnosis: "selected_not_used",
        relevant_information_stage: "selected",
        answer_usage: "not_used",
      },
    }).label).toBe("提示词与回答生成策略 / 行动步骤不清晰");
  });
});
