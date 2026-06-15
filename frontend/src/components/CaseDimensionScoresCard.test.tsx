import { describe, expect, it } from "vitest";
import { CaseDimensionScoresCard } from "./CaseDimensionScoresCard";
import { renderWithProviders } from "../test/renderWithProviders";

describe("CaseDimensionScoresCard", () => {
  it("matches snapshot", () => {
    const { container } = renderWithProviders(
      <CaseDimensionScoresCard
        dimensionScores={{ safety: 8, clarity: 6 }}
        dimensionMax={{ safety: 10, clarity: 10 }}
        scoreDeductions={["未提及就医建议"]}
        highlightKeywords={["胸痛"]}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
