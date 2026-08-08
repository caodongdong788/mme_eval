import { describe, expect, it } from "vitest";
import { buildCaseTypeOutcomeData } from "./caseTypeMetrics";

describe("buildCaseTypeOutcomeData", () => {
  it("builds success, failure and pass-rate values from case_type summary", () => {
    expect(
      buildCaseTypeOutcomeData({
        医学诊疗类: { total: 5, passed: 3 },
        情绪支持类: { total: 2, passed: 2 },
      })
    ).toEqual([
      { name: "医学诊疗类", total: 5, passed: 3, failed: 2, ratePct: 60 },
      { name: "情绪支持类", total: 2, passed: 2, failed: 0, ratePct: 100 },
    ]);
  });

  it("keeps invalid counters inside a safe display range", () => {
    expect(buildCaseTypeOutcomeData({ 异常数据: { total: 2, passed: 5 } })).toEqual([
      { name: "异常数据", total: 2, passed: 2, failed: 0, ratePct: 100 },
    ]);
  });
});
