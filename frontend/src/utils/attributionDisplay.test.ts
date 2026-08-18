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
      .toBe("第 1 次 RAG 检索 · 文献 2 · 片段 1与对话消息 2是证据");
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
    const category = (source: Parameters<typeof cxAgentSuggestionCategory>[0]) =>
      cxAgentSuggestionCategory(source).label;

    expect(category({ cause_code: "rag_not_called" })).toBe("RAG 优化 / 未触发检索");
    expect(category({ cause_code: "rag_call_failed" })).toBe("RAG 优化 / 调用失败");
    expect(category({ rag_diagnosis: { query_quality: "wrong" } })).toBe("RAG 优化 / Query 不完整或意图识别偏差");
    expect(category({ cause_code: "rag_recall_error" })).toBe("RAG 优化 / 召回覆盖不足");
    expect(category({ cause_code: "rag_threshold_error" })).toBe("RAG 优化 / 召回覆盖不足");
    expect(category({ cause_code: "rag_candidate_or_rerank_error" })).toBe("RAG 优化 / 排序或重排不当");
    expect(category({ cause_code: "rag_rerank_error" })).toBe("RAG 优化 / 排序或重排不当");
    expect(category({ cause_code: "rag_not_grounded" })).toBe("RAG 优化 / 已召回但未使用");
    expect(category({ rag_diagnosis: { answer_usage: "misinterpreted" } })).toBe("RAG 优化 / 证据误读");
    expect(category({ cause_code: "rag_corpus_gap" })).toBe("RAG 优化 / 召回覆盖不足");
    expect(category({ cause_code: "citation_mismatch" })).toBe("RAG 优化 / 缺少 RAG 引用");
    expect(category({ evaluation_issue_category: "missing_rag_reference" })).toBe("RAG 优化 / 缺少 RAG 引用");
  });

  it("covers context, tools, reasoning, delivery and runtime without text guessing", () => {
    const category = (source: Parameters<typeof cxAgentSuggestionCategory>[0]) =>
      cxAgentSuggestionCategory(source).label;

    expect(category({ cause_code: "context_not_fetched" })).toBe("Agent 工程链路 / Timeline 或用户事实未注入");
    expect(category({ cause_code: "context_not_used" })).toBe("Agent 工程链路 / 上下文已注入但未使用");
    expect(category({ cause_code: "tool_timeout" })).toBe("Agent 工程链路 / 工具执行失败");
    expect(category({ cause_code: "risk_benefit_error" })).toBe("Agent 决策与推理策略 / 风险识别不足");
    expect(category({ cause_code: "output_protocol_error" })).toBe("输出校验与安全守卫 / 未执行终答前检查");
    expect(category({ cause_code: "compaction_error" })).toBe("Agent 工程链路 / 上下文窗口或压缩异常");
    expect(category({ cause_code: "tool_result_truncated" })).toBe("Agent 工程链路 / 工具结果被截断");
    expect(category({ cause_code: "context_subject_error" })).toBe("Agent 工程链路 / 咨询对象归属错误");
    expect(category({ cause_code: "temporal_reasoning_error" })).toBe("Agent 决策与推理策略 / Timeline 时间顺序判断错误");
  });

  it("prefers validated structured classification over legacy owner fallbacks", () => {
    expect(cxAgentSuggestionCategory({
      owner: "generator",
      cause_code: "response_composition_error",
      optimization_classification: {
        domain: "clinical_reasoning",
        component: "contraindication",
        failure_mode: "contraindication_error",
        action_type: "clinical_reasoning",
        evidence_status: "sufficient",
      },
    }).label).toBe("Agent 决策与推理策略 / 禁忌或相互作用判断不足");
  });
});
