import { describe, expect, it } from "vitest";
import { guidelineMatch, scoringPointWeight } from "./caseJudging";

describe("caseJudging", () => {
  it("scoringPointWeight parses bracket weight", () => {
    expect(scoringPointWeight({ name: "x", passed: true, evidence: ["[w+3]"] })).toBe(3);
    expect(scoringPointWeight({ name: "x", passed: true })).toBeNull();
  });

  it("guidelineMatch computes anchored rate", () => {
    const detail = { case: { scoring_points: [{ guideline: "g1" }, {}, { guideline: "g2" }] } };
    const pts = [
      { name: "scoring_point.point0", passed: true },
      { name: "scoring_point.point2", passed: false },
    ];
    expect(guidelineMatch(detail, pts)).toEqual({ rate: 0.5, matched: 1, total: 2 });
  });
});
