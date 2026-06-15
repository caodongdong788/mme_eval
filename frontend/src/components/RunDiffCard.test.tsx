import { describe, expect, it, vi } from "vitest";
import { RunDiff } from "../api";
import { RunDiffCard } from "./RunDiffCard";
import { renderWithProviders } from "../test/renderWithProviders";

describe("RunDiffCard", () => {
  it("matches snapshot without diff", () => {
    const { container } = renderWithProviders(
      <RunDiffCard
        otherRuns={[{ id: 2, name: "上周基线", run_slug: "run-2", status: "success" } as never]}
        diff={null}
        onSelectBaseline={vi.fn()}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it("matches snapshot with diff result", () => {
    const { container } = renderWithProviders(
      <RunDiffCard
        otherRuns={[]}
        diff={
          {
            current: { id: 1, run_slug: "run-1", pass_rate: 0.8, passed: 8, total: 10 },
            against: { id: 2, run_slug: "run-2", pass_rate: 0.85, passed: 17, total: 20 },
            pass_rate_delta: -0.05,
            regressions: ["bc-001", "bc-002"],
            improvements: ["bc-003"],
            judge_logic_changed: true,
            fingerprint_changes: {},
          } as RunDiff
        }
        onSelectBaseline={vi.fn()}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
