import { describe, expect, it } from "vitest";
import {
  buildPassRateTrend,
  buildCxAgentOptimizationTrend,
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
    trigger_type: "manual",
    adapter_type: "openai_compat",
    total: 92,
    passed: 80,
    pass_rate: 0.87,
    medical_safety_failed: 0,
    n_runs: 1,
    error_msg: "",
    has_traces: true,
    pinned: false,
    evaluation_mode: "single_turn",
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
      run({ id: 1, pass_rate: 0.8, medical_safety_failed: 1, avg_composite: 30 }),
      run({ id: 2, pass_rate: 0.9, medical_safety_failed: 2, avg_composite: 36 }),
      run({ id: 3, status: "running", avg_composite: 40 }),
    ]);
    expect(kpis.total).toBe(3);
    expect(kpis.avgPassPct).toBe(85);
    expect(kpis.avgComposite).toBe(33);
    expect(kpis.medicalSafetyFailedTotal).toBe(3);
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

  it("builds one cx-agent optimization line per benchmark and aggregates latest comparisons", () => {
    const trend = buildCxAgentOptimizationTrend([
      run({ id: 1, benchmark_id: 10, benchmark_name: "真实患者", created_at: "2026-06-10T10:00:00Z", cx_agent_optimization_count: 4, cx_agent_p0_optimization_count: 1 }),
      run({ id: 2, benchmark_id: 10, benchmark_name: "真实患者", created_at: "2026-06-11T10:00:00Z", cx_agent_optimization_count: 6, cx_agent_p0_optimization_count: 2 }),
      run({ id: 3, benchmark_id: 20, benchmark_name: "合成对话", created_at: "2026-06-10T11:00:00Z", cx_agent_optimization_count: 10, cx_agent_p0_optimization_count: 3 }),
      run({ id: 4, benchmark_id: 20, benchmark_name: "合成对话", created_at: "2026-06-11T11:00:00Z", cx_agent_optimization_count: 12, cx_agent_p0_optimization_count: 4 }),
      run({ id: 5, benchmark_id: 20, benchmark_name: "合成对话", created_at: "2026-06-12T10:00:00Z", cx_agent_optimization_count: null }),
      run({ id: 6, status: "running", benchmark_id: 10, cx_agent_optimization_count: 2 }),
    ]);
    expect(trend.series).toEqual([
      expect.objectContaining({ name: "合成对话", latest: 12, previous: 10, latestP0: 4, previousP0: 3 }),
      expect.objectContaining({ name: "真实患者", latest: 6, previous: 4, latestP0: 2, previousP0: 1 }),
    ]);
    expect(trend.points).toHaveLength(4);
    expect(trend.points).toContainEqual(
      expect.objectContaining({ runId: 4, optimizationCount: 12, p0OptimizationCount: 4 })
    );
    expect(trend.latestTotal).toBe(18);
    expect(trend.latestP0Total).toBe(6);
    expect(trend.previousTotal).toBe(14);
    expect(trend.delta).toBe(4);
  });

  it("does not compare benchmark totals until every benchmark has a previous result", () => {
    const trend = buildCxAgentOptimizationTrend([
      run({ id: 1, benchmark_id: 10, benchmark_name: "真实患者", created_at: "2026-06-10T10:00:00Z", cx_agent_optimization_count: 4 }),
      run({ id: 2, benchmark_id: 10, benchmark_name: "真实患者", created_at: "2026-06-11T10:00:00Z", cx_agent_optimization_count: 6 }),
      run({ id: 3, benchmark_id: 20, benchmark_name: "合成对话", created_at: "2026-06-11T11:00:00Z", cx_agent_optimization_count: 12 }),
    ]);
    expect(trend.latestTotal).toBe(18);
    expect(trend.latestP0Total).toBe(0);
    expect(trend.previousTotal).toBeNull();
    expect(trend.delta).toBeNull();
  });

  it("computeRunsPeriodDeltas compares two windows", () => {
    const current = [
      run({ id: 1, pass_rate: 0.9, medical_safety_failed: 1, avg_composite: 36 }),
      run({ id: 2, pass_rate: 0.7, medical_safety_failed: 0, avg_composite: 30 }),
    ];
    const previous = [run({ id: 3, pass_rate: 0.6, medical_safety_failed: 2, avg_composite: 27 })];
    expect(computeRunsPeriodDeltas(current, previous)).toEqual({
      total: 1,
      passRatePct: 20,
      avgComposite: 6,
      medicalSafetyFailed: -1,
    });
  });
});
