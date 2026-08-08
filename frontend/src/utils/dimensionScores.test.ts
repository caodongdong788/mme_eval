import { describe, expect, it } from "vitest";
import { buildDimensionScoreData } from "./dimensionScores";

describe("buildDimensionScoreData", () => {
  it("rounds dimension averages to two decimals", () => {
    expect(
      buildDimensionScoreData(
        { medical_safety: 2.5396825396825395 },
        { medical_safety: "医学安全性" }
      )
    ).toEqual([{ name: "医学安全性", value: 2.54 }]);
  });

  it("does not turn missing or invalid averages into zero scores", () => {
    expect(
      buildDimensionScoreData(
        { missing: null, invalid: Number.NaN, valid: 0 },
        {}
      )
    ).toEqual([{ name: "valid", value: 0 }]);
  });
});
