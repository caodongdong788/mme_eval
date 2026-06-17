import { describe, expect, it } from "vitest";
import { computeLaunchCaseCount, countCasesByLevel } from "./launchCaseCount";

const CASES = [
  { level: "L1" },
  { level: "L1" },
  { level: "L2" },
  { level: "L3" },
];

describe("computeLaunchCaseCount", () => {
  it("returns all cases when no level filter and limit is 0", () => {
    expect(computeLaunchCaseCount(CASES, [], 0)).toBe(4);
  });

  it("filters by selected levels", () => {
    expect(computeLaunchCaseCount(CASES, ["L1"], 0)).toBe(2);
    expect(computeLaunchCaseCount(CASES, ["L1", "L3"], 0)).toBe(3);
  });

  it("applies limit after level filter", () => {
    expect(computeLaunchCaseCount(CASES, ["L1"], 1)).toBe(1);
    expect(computeLaunchCaseCount(CASES, [], 2)).toBe(2);
  });
});

describe("countCasesByLevel", () => {
  it("aggregates per level", () => {
    expect(countCasesByLevel(CASES)).toEqual({ L1: 2, L2: 1, L3: 1 });
  });
});
