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
        dimensionReferenceAnswers={{ empathy: ["先回应患者担忧，再给出可执行的下一步。"] }}
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
    expect(screen.getByText("扣分原因")).toBeInTheDocument();
    expect(screen.getByText("指南 warm_response -1分：缺少针对性情绪承接")).toBeInTheDocument();
    expect(screen.getByText("维度评分")).toBeInTheDocument();
    expect(screen.getByText("好答案参考")).toBeInTheDocument();
    expect(screen.getByText("先回应患者担忧，再给出可执行的下一步。")).toBeInTheDocument();
    expect(screen.getByText("维度")).toBeInTheDocument();
    expect(screen.queryByText("guideline.seek_care")).not.toBeInTheDocument();
    expect(screen.queryByText("1/3")).not.toBeInTheDocument();
    await waitFor(() => expect(mockedApi.getJudgeVerdictLabels).toHaveBeenCalled());
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
