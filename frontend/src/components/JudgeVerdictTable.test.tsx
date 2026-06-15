import { describe, expect, it } from "vitest";
import { JudgeVerdictTable } from "./JudgeVerdictTable";
import { renderWithProviders } from "../test/renderWithProviders";

describe("JudgeVerdictTable", () => {
  it("matches snapshot", () => {
    const { container } = renderWithProviders(
      <JudgeVerdictTable
        tagLabel={(t) => t}
        verdicts={[
          {
            name: "llm.empathy",
            passed: true,
            score: 4,
            max_score: 5,
            reason: "表达关切",
            failure_tags: [],
            adjudicated: false,
          },
          {
            name: "hard_gate.red_flag",
            passed: false,
            score: 0,
            max_score: 1,
            reason: "未识别红旗",
            failure_tags: ["missed_red_flag"],
            adjudicated: true,
          },
        ]}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
