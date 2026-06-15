import { describe, expect, it } from "vitest";
import { formatJudgeDefaultLabel } from "./judgeDefault";

describe("formatJudgeDefaultLabel", () => {
  it("formats provider and model", () => {
    expect(
      formatJudgeDefaultLabel({
        provider: "azure",
        model: "gpt-5.1",
        base_url: "",
        api_version: "",
        model_options: [],
      })
    ).toBe("azure · gpt-5.1");
  });

  it("returns null when model missing", () => {
    expect(formatJudgeDefaultLabel({ provider: "azure", model: "", base_url: "", api_version: "", model_options: [] })).toBeNull();
  });
});
