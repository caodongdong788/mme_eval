import { describe, expect, it } from "vitest";
import {
  buildPassRateTrend,
  computeRunsListKpis,
  computeRunsPeriodDeltas,
  countRunsByFilter,
  filterRuns,
} from "./runsListOverview";
import type { RunSummary } from "../api/types";

function run(partial: Partial<RunSummary> & { id: number }): RunSummary {
  return {
    run_slug: `run_${partial.id}`,
    name: `run_${partial.id}`,
    status: "success",
    adapter_type: "openai_compat",
    total: 92,
    passed: 80,
    pass_rate: 0.87,
    hard_gate_failed: 0,
    n_runs: 1,
    error_msg: "",
    has_traces: true,
    pinned: false,
    ...partial,
  };
}

describe("runsListOverview", () => {
  it("filterRuns respects pinned and status", () => {
    const runs = [
      run({ id: 1, pinned: true }),
      run({ id: 2, status: "running" }),
      run({ id: 3, status: "failed" }),
    ];
    expect(filterRuns(runs, "pinned")).toHaveLength(1);
    expect(filterRuns(runs, "running")).toHaveLength(1);
    expect(filterRuns(runs, "failed")).toHaveLength(1);
  });

  it("countRunsByFilter tallies each tab", () => {
    const runs = [
      run({ id: 1, pinned: true }),
      run({ id: 2, status: "running" }),
      run({ id: 3, status: "failed" }),
      run({ id: 4 }),
    ];
    expect(countRunsByFilter(runs)).toEqual({
      all: 4,
      success: 2,
      running: 1,
      failed: 1,
      pinned: 1,
    });
  });

  it("computeRunsListKpis aggregates success runs", () => {
    const kpis = computeRunsListKpis([
      run({ id: 1, pass_rate: 0.8, hard_gate_failed: 1 }),
      run({ id: 2, pass_rate: 0.9, hard_gate_failed: 2 }),
      run({ id: 3, status: "running" }),
    ]);
    expect(kpis.total).toBe(3);
    expect(kpis.avgPassPct).toBe(85);
    expect(kpis.hardGateTotal).toBe(3);
    expect(kpis.activeCount).toBe(1);
  });

  it("buildPassRateTrend returns chronological points", () => {
    const trend = buildPassRateTrend([
      run({ id: 1, pass_rate: 0.8, created_at: "2026-06-10T10:00:00Z" }),
      run({ id: 2, pass_rate: 0.9, created_at: "2026-06-16T10:00:00Z" }),
    ]);
    expect(trend).toHaveLength(2);
    expect(trend[0].passPct).toBe(80);
    expect(trend[1].passPct).toBe(90);
  });

  it("computeRunsPeriodDeltas compares two windows", () => {
    const current = [
      run({ id: 1, pass_rate: 0.9, hard_gate_failed: 1 }),
      run({ id: 2, pass_rate: 0.7, hard_gate_failed: 0 }),
    ];
    const previous = [run({ id: 3, pass_rate: 0.6, hard_gate_failed: 2 })];
    expect(computeRunsPeriodDeltas(current, previous)).toEqual({
      total: 1,
      passRatePct: 20,
      hardGate: -1,
      active: 0,
    });
  });
});
