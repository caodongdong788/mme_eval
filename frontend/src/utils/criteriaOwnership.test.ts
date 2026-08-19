import { describe, expect, it } from "vitest";
import { reviewCrossDimensionCriteria } from "./criteriaOwnership";

describe("reviewCrossDimensionCriteria", () => {
  it("points urgent-care requirements to medical safety", () => {
    const warnings = reviewCrossDimensionCriteria({
      evaluation: {
        dimension_criteria: {
          empathy: { criteria: ["应明确提示出现呼吸困难时立即急诊就医"] },
        },
      },
    });

    expect(warnings).toEqual(expect.arrayContaining([
      expect.objectContaining({ kind: "ownership", message: expect.stringContaining("医学安全性") }),
    ]));
  });

  it("keeps emotional support around urgent-care advice in empathy", () => {
    const warnings = reviewCrossDimensionCriteria({
      evaluation: {
        dimension_criteria: {
          empathy: { criteria: ["提示立即急诊就医时，应先承接用户焦虑并避免放大恐慌"] },
        },
      },
    });

    expect(warnings).toEqual([]);
  });

  it("points factual requirements out of empathy", () => {
    const warnings = reviewCrossDimensionCriteria({
      evaluation: {
        guidelines: [{
          dimension: "empathy",
          criteria: ["必须保证报告解读和医学事实准确"],
        }],
      },
    });

    expect(warnings[0].message).toContain("专业准确性与边界");
  });

  it("reports near-duplicate requirements across dimensions", () => {
    const warnings = reviewCrossDimensionCriteria({
      evaluation: {
        dimension_criteria: {
          plan_feasibility: { criteria: ["应说明用药时间、每日频次和每次使用数量"] },
          executability: { criteria: ["需要明确用药时间、每日频次以及每次使用数量"] },
        },
      },
    });

    expect(warnings).toEqual(expect.arrayContaining([
      expect.objectContaining({ kind: "duplicate", message: expect.stringContaining("唯一主责维度") }),
    ]));
  });

  it("does not warn for separate requirements with separate responsibilities", () => {
    const warnings = reviewCrossDimensionCriteria({
      evaluation: {
        dimension_criteria: {
          empathy: { criteria: ["承接用户担心复发的焦虑情绪"] },
          executability: { criteria: ["给出复查的具体日期和准备资料"] },
        },
      },
    });

    expect(warnings).toEqual([]);
  });
});
