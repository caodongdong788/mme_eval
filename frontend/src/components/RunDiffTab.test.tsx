import { describe, expect, it, vi } from "vitest";
import { DiffCaseRow, RunDiff } from "../api/index";
import { RunDiffTab } from "./RunDiffTab";
import { renderWithProviders } from "../test/renderWithProviders";

const otherRuns = [{ id: 2, name: "上周基线", run_slug: "run-2", status: "success" } as never];

const diffCases: DiffCaseRow[] = [
  {
    sample_id: "bc-001",
    scenario: "s1",
    sub_scenario: "场景1",
    level: "L1",
    current_release_passed: false,
    baseline_release_passed: true,
    current_score: 0.6,
    baseline_score: 0.85,
    score_delta: -0.25,
    change: "regression",
  },
  {
    sample_id: "bc-003",
    scenario: "s2",
    sub_scenario: "场景3",
    level: "L2",
    current_release_passed: true,
    baseline_release_passed: false,
    current_score: 0.9,
    baseline_score: 0.5,
    score_delta: 0.4,
    change: "improvement",
  },
];

describe("RunDiffTab", () => {
  it("matches snapshot without diff", () => {
    const { container } = renderWithProviders(
      <RunDiffTab
        runId={1}
        otherRuns={otherRuns}
        diff={null}
        diffBaselineId={null}
        diffLoading={false}
        onSelectBaseline={vi.fn()}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it("matches snapshot with diff result", () => {
    const { container } = renderWithProviders(
      <RunDiffTab
        runId={1}
        otherRuns={[]}
        diff={
          {
            current: { id: 1, run_slug: "run-1", pass_rate: 0.8, passed: 8, total: 10 },
            against: { id: 2, run_slug: "run-2", pass_rate: 0.85, passed: 17, total: 20 },
            pass_rate_delta: -0.05,
            regressions: ["bc-001"],
            improvements: ["bc-003"],
            judge_logic_changed: true,
            fingerprint_changes: {},
            cases: diffCases,
          } as RunDiff
        }
        diffBaselineId={2}
        diffLoading={false}
        onSelectBaseline={vi.fn()}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
