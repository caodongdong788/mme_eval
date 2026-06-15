import { describe, expect, it } from "vitest";
import { ScoringPointsTable } from "./ScoringPointsTable";
import { renderWithProviders } from "../test/renderWithProviders";

describe("ScoringPointsTable", () => {
  it("matches snapshot for scoring points", () => {
    const { container } = renderWithProviders(
      <ScoringPointsTable
        scoringPoints={[
          {
            name: "scoring_point.point0",
            passed: true,
            score: 2,
            max_score: 2,
            evidence: ["[✓ +2] 给出就医建议"],
          },
          {
            name: "scoring_point.point1",
            passed: false,
            score: 0,
            max_score: 0,
            evidence: ["[✓ -3] 错误处方"],
            reason: "提及具体药名",
          },
        ]}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it("renders nothing when empty", () => {
    const { container } = renderWithProviders(<ScoringPointsTable scoringPoints={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
