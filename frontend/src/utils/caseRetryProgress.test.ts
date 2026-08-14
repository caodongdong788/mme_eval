import { describe, expect, it } from "vitest";
import { isActiveCaseRetry } from "./caseRetryProgress";

describe("isActiveCaseRetry", () => {
  it("restores progress only for the retry target case", () => {
    const progress = {
      status: "running",
      progress: {
        percent: 35,
        context: { kind: "case_retry", sample_id: "case_55" },
      },
    };

    expect(isActiveCaseRetry(progress, "case_55")).toBe(true);
    expect(isActiveCaseRetry(progress, "case_56")).toBe(false);
  });

  it("does not restore a completed or non-retry job", () => {
    expect(
      isActiveCaseRetry(
        {
          status: "success",
          progress: { context: { kind: "case_retry", sample_id: "case_55" } },
        },
        "case_55"
      )
    ).toBe(false);
    expect(
      isActiveCaseRetry(
        {
          status: "running",
          progress: { context: { kind: "full_run", sample_id: "case_55" } },
        },
        "case_55"
      )
    ).toBe(false);
  });

  it("recognizes every selected case during a batch retry", () => {
    const progress = {
      status: "running",
      progress: { context: { kind: "cases_retry", sample_ids: ["case_12", "case_14"] } },
    };

    expect(isActiveCaseRetry(progress, "case_12")).toBe(true);
    expect(isActiveCaseRetry(progress, "case_14")).toBe(true);
    expect(isActiveCaseRetry(progress, "case_16")).toBe(false);
  });
});
