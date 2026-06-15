import { describe, expect, it } from "vitest";
import { fallbackJudgeLabel, guidelineMatch, scoringPointWeight } from "./caseJudging";

describe("caseJudging", () => {
  it("fallbackJudgeLabel maps prefix and suffix", () => {
    expect(fallbackJudgeLabel("llm.empathy")).toBe("体验·共情");
    expect(fallbackJudgeLabel("llm.triage_quality")).toBe("体验·分诊建议");
    expect(fallbackJudgeLabel("hard_gate")).toBe("硬门槛");
    expect(fallbackJudgeLabel(undefined)).toBe("-");
  });

  it("scoringPointWeight parses signed weight from evidence", () => {
    expect(
      scoringPointWeight({
        name: "scoring_point.point0",
        passed: false,
        evidence: ["[✓ -3] 判据说明"],
      })
    ).toBe(-3);
    expect(
      scoringPointWeight({ name: "scoring_point.point1", passed: true, evidence: [] })
    ).toBeNull();
  });

  it("guidelineMatch counts anchored scoring points", () => {
    const detail = {
      case: {
        scoring_points: [{ guideline: "g1" }, {}, { guideline: "g2" }],
      },
    };
    const scoringPoints = [
      { name: "scoring_point.point0", passed: true },
      { name: "scoring_point.point2", passed: false },
    ];
    expect(guidelineMatch(detail, scoringPoints)).toEqual({
      rate: 0.5,
      matched: 1,
      total: 2,
    });
    expect(guidelineMatch({ case: { scoring_points: [{}] } }, [])).toBeNull();
  });
});
