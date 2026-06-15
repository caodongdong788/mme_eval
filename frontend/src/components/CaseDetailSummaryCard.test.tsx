import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { CaseDetailSummaryCard } from "./CaseDetailSummaryCard";
import { renderWithProviders } from "../test/renderWithProviders";

describe("CaseDetailSummaryCard", () => {
  it("matches snapshot", () => {
    const { container } = renderWithProviders(
      <MemoryRouter>
        <CaseDetailSummaryCard
          detail={{
            case: { sample_id: "bc-001", sub_scenario: "红旗分诊", level: "L2" },
            score_profile: "standard",
            composite_score: 0.82,
            grade: "B",
            stability: "stable_pass",
            hard_gate_passed: true,
            gate_passed: true,
            release_passed: false,
            needs_human_review: true,
          }}
          scoringPoints={[]}
          backTo="/runs/1"
          backLabel="用例列表"
        />
      </MemoryRouter>
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
