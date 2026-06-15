import { describe, expect, it } from "vitest";
import { RunDetail } from "../api/index";
import { RunOverviewKpiGrid } from "./RunOverviewKpiGrid";
import { renderWithProviders } from "../test/renderWithProviders";

const baseRun = {
  id: 1,
  name: "基准回归",
  status: "success",
  total: 10,
  passed: 8,
  pass_rate: 0.8,
  pass_rate_ci: { low: 0.5, high: 0.95, confidence: 0.95 },
  hard_gate_failed: 1,
  n_runs: 3,
  stability_distribution: { stable_pass: 7, flaky: 1, stable_fail: 2 },
  grading: { avg_composite: 0.876 },
} as unknown as RunDetail;

describe("RunOverviewKpiGrid", () => {
  it("matches snapshot", () => {
    const { container } = renderWithProviders(
      <RunOverviewKpiGrid
        run={baseRun}
        reviewStats={{
          queue_total: 2,
          pending: 1,
          reviewed: 1,
          agree: 1,
          override: 0,
          agree_rate: 0.5,
          disagree_rate: 0,
        }}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
