import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { JudgeVerdictTable } from "./JudgeVerdictTable";
import { renderWithProviders } from "../test/renderWithProviders";

describe("JudgeVerdictTable", () => {
  it("shows final dimension score and guideline deduction in the judge row", () => {
    renderWithProviders(
      <JudgeVerdictTable
        tagLabel={(t) => t}
        dimensionScores={{ empathy: 3 }}
        dimensionMax={{ empathy: 5 }}
        scoreDeductions={["empathy 指南 warm_response -1分：缺少针对性情绪承接"]}
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

    expect(screen.getByText("3/5")).toBeInTheDocument();
    expect(screen.getByText("扣分原因")).toBeInTheDocument();
    expect(screen.getByText("指南 warm_response -1分：缺少针对性情绪承接")).toBeInTheDocument();
    expect(screen.getByText("维度评分")).toBeInTheDocument();
    expect(screen.getByText("维度")).toBeInTheDocument();
    expect(screen.queryByText("guideline.seek_care")).not.toBeInTheDocument();
    expect(screen.queryByText("1/3")).not.toBeInTheDocument();
  });
});
