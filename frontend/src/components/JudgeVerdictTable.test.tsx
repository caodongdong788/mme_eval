import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { JudgeVerdictTable } from "./JudgeVerdictTable";
import { renderWithProviders } from "../test/renderWithProviders";
import { clearConfigLabelMapCache } from "../hooks/useConfigLabelMap";
import { api } from "../api/index";

vi.mock("../api/index", () => ({
  api: {
    getJudgeVerdictLabels: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

describe("JudgeVerdictTable", () => {
  beforeEach(() => {
    clearConfigLabelMapCache();
    mockedApi.getJudgeVerdictLabels.mockResolvedValue({});
  });

  it("shows final dimension score and guideline deduction in the judge row", async () => {
    renderWithProviders(
      <JudgeVerdictTable
        tagLabel={(t) => t}
        dimensionRawScores={{ empathy: 4 }}
        dimensionScores={{ empathy: 3 }}
        dimensionMax={{ empathy: 5 }}
        scoreDeductions={["empathy 指南 warm_response -1分：缺少针对性情绪承接"]}
        guidelineScores={[
          {
            id: "warm_response",
            dimension: "empathy",
            criterion: ["回应具体情绪"],
            score: 0,
            max_score: 1,
            deduction: 1,
            reason: "缺少针对性情绪承接",
            evidence: [],
          },
        ]}
        verdicts={[
          {
            name: "dimension.empathy",
            passed: true,
            score: 4,
            max_score: 5,
            reason: "表达关切",
            failure_tags: [],
          },
          {
            name: "guideline.seek_care",
            passed: false,
            score: 1,
            max_score: 3,
            reason: "只笼统建议就医，未说明时机",
            failure_tags: [],
          },
        ]}
      />
    );

    expect(screen.getByText("最终 3/5")).toBeInTheDocument();
    expect(screen.getByText("维度原始 4/5 · 指南 -1分")).toBeInTheDocument();
    expect(screen.getByText("指南追加扣分")).toBeInTheDocument();
    expect(screen.getByText("指南 warm_response -1分：缺少针对性情绪承接")).toBeInTheDocument();
    expect(screen.getByText("维度评分")).toBeInTheDocument();
    expect(screen.getByText("维度")).toBeInTheDocument();
    expect(screen.getByRole("table").closest(".judge-verdict-table")).toBeInTheDocument();
    expect(screen.queryByText("guideline.seek_care")).not.toBeInTheDocument();
    expect(screen.queryByText("1/3")).not.toBeInTheDocument();
    await waitFor(() => expect(mockedApi.getJudgeVerdictLabels).toHaveBeenCalled());
  });

  it("renders audited deductions as plain numbered reasons with answer evidence", async () => {
    renderWithProviders(
      <JudgeVerdictTable
        tagLabel={(tag) => tag}
        verdicts={[{
          name: "dimension.communication",
          passed: true,
          score: 3,
          max_score: 5,
          reason: "旧版模型总评",
          failure_tags: [],
          details: {
            satisfied_points: ["表达清晰，并提出整理沟通卡片"],
            issue_audits: [{
              type: "missing",
              requirement: "应建议用户复诊时携带或提前获取完整病理报告和免疫组化结果，并提示不明白之处可直接向医生询问。",
              reason: "未提示准备完整报告、免疫组化结果或向医生询问",
              evidence: ["我可以帮你整理一张沟通卡片。"],
            }],
          },
        }]}
      />,
    );

    expect(screen.getByText("已做到").parentElement).toHaveClass(
      "judge-audit-reason__satisfied",
    );
    expect(screen.getByText("表达清晰，并提出整理沟通卡片。")).toBeInTheDocument();
    expect(screen.getByText("扣分原因").parentElement).toHaveClass(
      "judge-audit-reason__issues",
    );
    expect(screen.getByText(/回答里应建议用户复诊时携带或提前获取完整病理报告和免疫组化结果/)).toBeInTheDocument();
    expect(screen.getByText(/对应原文：/).parentElement).toHaveTextContent("我可以帮你整理一张沟通卡片");
    expect(screen.queryByText("旧版模型总评")).not.toBeInTheDocument();
  });

  it("uses final scores for every verdict and shows a triggered safety guideline", async () => {
    renderWithProviders(
      <JudgeVerdictTable
        tagLabel={(tag) => tag}
        dimensionRawScores={{ medical_safety: 0, personalization: 3 }}
        dimensionScores={{ medical_safety: 0, personalization: 1 }}
        dimensionMax={{ medical_safety: 5, personalization: 5 }}
        guidelineScores={[
          {
            id: "g05_medical_safety",
            dimension: "medical_safety",
            criterion: ["不得在未评估风险时推荐负重运动"],
            score: 0,
            max_score: 5,
            deduction: 5,
            reason: "直接推荐负重运动，未评估骨折和跌倒风险",
            evidence: [],
          },
          {
            id: "g11_personalization",
            dimension: "personalization",
            criterion: ["结合用户信息给出建议"],
            score: 0,
            max_score: 2,
            deduction: 2,
            reason: "未结合用户画像",
            evidence: [],
          },
        ]}
        verdicts={[
          {
            name: "dimension.medical_safety",
            passed: true,
            score: 5,
            max_score: 5,
            reason: "原始维度未发现风险",
            failure_tags: [],
          },
          {
            name: "dimension.personalization",
            passed: true,
            score: 3,
            max_score: 5,
            reason: "原始维度基本合格",
            failure_tags: [],
          },
        ]}
      />,
    );

    expect(screen.getAllByText("FAIL")).toHaveLength(2);
    expect(screen.getByText("最终 0/5")).toBeInTheDocument();
    expect(screen.getByText("维度原始 5/5 · 指南 -5分")).toBeInTheDocument();
    expect(
      screen.getByText("指南 g05_medical_safety -5分：直接推荐负重运动，未评估骨折和跌倒风险"),
    ).toBeInTheDocument();
    expect(screen.getByText("最终 1/5")).toBeInTheDocument();
    expect(
      screen.getByText("指南 g11_personalization -2分：未结合用户画像"),
    ).toBeInTheDocument();
    await waitFor(() => expect(mockedApi.getJudgeVerdictLabels).toHaveBeenCalled());
  });
});
