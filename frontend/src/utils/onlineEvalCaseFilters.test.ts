import { describe, expect, it } from "vitest";
import {
  filterOnlineEvalCasesBySelection,
  matchesOnlineEvalGateFilter,
  matchesOnlineEvalGradeFilter,
  matchesOnlineEvalRoleScoreFilter,
  matchesOnlineEvalScoreFilter,
} from "./onlineEvalCaseFilters";

describe("onlineEvalCaseFilters", () => {
  it("matches gate status exactly", () => {
    expect(matchesOnlineEvalGateFilter("pass", { gate_status: "pass" })).toBe(true);
    expect(matchesOnlineEvalGateFilter("fail", { gate_status: "pass" })).toBe(false);
  });

  it("matches grade exactly", () => {
    expect(matchesOnlineEvalGradeFilter("good", { grade: "good" })).toBe(true);
    expect(matchesOnlineEvalGradeFilter("unqualified", { grade: "qualified" })).toBe(false);
  });

  it("matches score buckets with inclusive lower bounds", () => {
    expect(matchesOnlineEvalScoreFilter("gte40_5", { total_score: 40.5 })).toBe(true);
    expect(matchesOnlineEvalScoreFilter("gte40_5", { total_score: 40.4 })).toBe(false);
    expect(matchesOnlineEvalScoreFilter("36to40_5", { total_score: 36 })).toBe(true);
    expect(matchesOnlineEvalScoreFilter("36to40_5", { total_score: 40.5 })).toBe(false);
    expect(matchesOnlineEvalScoreFilter("27to36", { total_score: 35.9 })).toBe(true);
    expect(matchesOnlineEvalScoreFilter("lt27", { total_score: 26.9 })).toBe(true);
    expect(matchesOnlineEvalScoreFilter("lt27", { total_score: 27 })).toBe(false);
  });

  it("matches role score buckets on 15-point subtotals", () => {
    expect(
      matchesOnlineEvalRoleScoreFilter(
        "gte13_5",
        { score_breakdown: { doctor_score: 13.5 } },
        "doctor_score"
      )
    ).toBe(true);
    expect(
      matchesOnlineEvalRoleScoreFilter(
        "12to13_5",
        { score_breakdown: { nurse_score: 13.5 } },
        "nurse_score"
      )
    ).toBe(false);
    expect(
      matchesOnlineEvalRoleScoreFilter(
        "9to12",
        { score_breakdown: { patient_score: 11.9 } },
        "patient_score"
      )
    ).toBe(true);
    expect(
      matchesOnlineEvalRoleScoreFilter(
        "lt9",
        { score_breakdown: { doctor_score: 9 } },
        "doctor_score"
      )
    ).toBe(false);
  });

  it("filters cases with AND across columns and OR inside a column", () => {
    const rows = [
      { gate_status: "pass", total_score: 42, grade: "excellent" },
      { gate_status: "pass", total_score: 39, grade: "good" },
      { gate_status: "fail", total_score: 0, grade: "unqualified" },
    ];
    expect(
      filterOnlineEvalCasesBySelection(rows, {
        gate_status: ["pass"],
        score_bucket: ["gte40_5", "36to40_5"],
        grade: ["excellent", "good"],
      })
    ).toHaveLength(2);
    expect(
      filterOnlineEvalCasesBySelection(rows, {
        gate_status: ["pass"],
        score_bucket: ["gte40_5"],
        grade: ["good"],
      })
    ).toHaveLength(0);
  });
});
