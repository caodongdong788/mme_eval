import { describe, expect, it } from "vitest";
import {
  filterOnlineEvalCasesBySelection,
  matchesOnlineEvalGateFilter,
  matchesOnlineEvalGradeFilter,
  matchesOnlineEvalScoreFilter,
} from "./onlineEvalCaseFilters";

describe("onlineEvalCaseFilters", () => {
  it("matches gate status exactly", () => {
    expect(matchesOnlineEvalGateFilter("pass", { gate_status: "pass" })).toBe(true);
    expect(matchesOnlineEvalGateFilter("fail", { gate_status: "pass" })).toBe(false);
  });

  it("matches grade exactly", () => {
    expect(matchesOnlineEvalGradeFilter("high_quality", { grade: "high_quality" })).toBe(true);
    expect(matchesOnlineEvalGradeFilter("fail", { grade: "acceptable" })).toBe(false);
  });

  it("matches score buckets with inclusive lower bounds", () => {
    expect(matchesOnlineEvalScoreFilter("gte9", { total_score_10: 9 })).toBe(true);
    expect(matchesOnlineEvalScoreFilter("gte9", { total_score_10: 8.9 })).toBe(false);
    expect(matchesOnlineEvalScoreFilter("8to9", { total_score_10: 8 })).toBe(true);
    expect(matchesOnlineEvalScoreFilter("8to9", { total_score_10: 9 })).toBe(false);
    expect(matchesOnlineEvalScoreFilter("7to8", { total_score_10: 7.9 })).toBe(true);
    expect(matchesOnlineEvalScoreFilter("6to7", { total_score_10: 6 })).toBe(true);
    expect(matchesOnlineEvalScoreFilter("lt6", { total_score_10: 5.9 })).toBe(true);
    expect(matchesOnlineEvalScoreFilter("lt6", { total_score_10: 6 })).toBe(false);
  });

  it("filters cases with AND across columns and OR inside a column", () => {
    const rows = [
      { gate_status: "pass", total_score_10: 9.1, grade: "excellent" },
      { gate_status: "pass", total_score_10: 8.4, grade: "high_quality" },
      { gate_status: "fail", total_score_10: 9.3, grade: "fail" },
    ];
    expect(
      filterOnlineEvalCasesBySelection(rows, {
        gate_status: ["pass"],
        score_bucket: ["gte9", "8to9"],
        grade: ["excellent", "high_quality"],
      })
    ).toHaveLength(2);
    expect(
      filterOnlineEvalCasesBySelection(rows, {
        gate_status: ["pass"],
        score_bucket: ["gte9"],
        grade: ["high_quality"],
      })
    ).toHaveLength(0);
  });
});
