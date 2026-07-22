import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "../test/renderWithProviders";
import { GuidelineScoresTable } from "./GuidelineScoresTable";

describe("GuidelineScoresTable", () => {
  it("renders guideline scoring details", () => {
    renderWithProviders(
      <GuidelineScoresTable
        scores={[
          {
            id: "next_step",
            dimension: "executability",
            criterion: "建议及时联系治疗团队评估",
            score: 2,
            max_score: 3,
            reason: "部分覆盖",
            evidence: ["建议尽快联系医生"],
          },
        ]}
      />
    );

    expect(screen.getByText("指南覆盖评分")).toBeInTheDocument();
    expect(screen.getByText("指南项")).toBeInTheDocument();
    expect(screen.getByText("绑定维度")).toBeInTheDocument();
    expect(screen.getByText("得分")).toBeInTheDocument();
    expect(screen.getByText("判定理由")).toBeInTheDocument();
  });
});
