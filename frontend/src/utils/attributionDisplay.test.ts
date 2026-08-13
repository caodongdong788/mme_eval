import { describe, expect, it } from "vitest";
import type { AttributionDeductionAnalysis } from "../api";
import {
  answerUsageDisplayName,
  attributionDeductionLabel,
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
  });

  it("turns RAG diagnostic enums into user-facing language", () => {
    expect(queryQualityDisplayName("good")).toBe("查询准确");
    expect(informationStageDisplayName("selected")).toBe("最终选中文献");
    expect(answerUsageDisplayName("used")).toBe("已正确使用");
  });
});
