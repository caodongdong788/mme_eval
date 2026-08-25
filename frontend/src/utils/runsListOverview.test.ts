import { describe, expect, it } from "vitest";
import {
  buildPassRateTrend,
  buildCxAgentOptimizationTrend,
  computeCxAgentOptimizationPeriodDeltas,
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
      run({
        id: 1, benchmark_id: 10, total: 100, passed: 80,
        created_at: "2026-06-10T10:00:00Z", medical_safety_failed: 1, avg_composite: 30,
      }),
      run({
        id: 2, benchmark_id: 20, total: 100, passed: 90,
        created_at: "2026-06-10T11:00:00Z", medical_safety_failed: 2, avg_composite: 36,
      }),
      run({ id: 3, status: "running", avg_composite: 40 }),
    ]);
    expect(kpis.total).toBe(3);
    expect(kpis.avgPassPct).toBe(85);
    expect(kpis.avgComposite).toBe(33);
    expect(kpis.medicalSafetyFailedTotal).toBe(3);
  });

  it("buildPassRateTrend aggregates the latest run of every benchmark into one daily point", () => {
    const trend = buildPassRateTrend([
      run({ id: 1, benchmark_id: 10, total: 100, passed: 80, created_at: "2026-06-10T09:00:00Z" }),
      run({ id: 2, benchmark_id: 10, total: 100, passed: 90, created_at: "2026-06-10T11:00:00Z" }),
      run({ id: 3, benchmark_id: 20, total: 50, passed: 30, created_at: "2026-06-10T10:00:00Z" }),
      run({ id: 4, benchmark_id: 20, total: 50, passed: 40, created_at: "2026-06-10T12:00:00Z" }),
      run({ id: 5, benchmark_id: 10, total: 100, passed: 70, created_at: "2026-06-11T10:00:00Z" }),
      run({ id: 6, benchmark_id: 20, total: 50, passed: 35, created_at: "2026-06-11T11:00:00Z" }),
    ]);
    expect(trend.points).toHaveLength(2);
    expect(trend.points[0]).toEqual(expect.objectContaining({
      label: "06-10",
      passPct: 86.7,
      passed: 130,
      total: 150,
    }));
    expect(trend.points[1]).toEqual(expect.objectContaining({
      label: "06-11",
      passPct: 70,
      passed: 105,
      total: 150,
    }));
    expect(trend.dateTicks).toEqual([
      new Date("2026-06-10T00:00:00").getTime(),
      new Date("2026-06-11T00:00:00").getTime(),
    ]);
    expect(trend.xDomain).toEqual([
      new Date("2026-06-10T00:00:00").getTime(),
      new Date("2026-06-11T23:59:59.999").getTime(),
    ]);
  });

  it("buildPassRateTrend omits dates until every benchmark has a completed result", () => {
    const trend = buildPassRateTrend([
      run({ id: 1, benchmark_id: 10, created_at: "2026-06-10T10:00:00Z" }),
      run({ id: 2, benchmark_id: 10, created_at: "2026-06-11T10:00:00Z" }),
      run({ id: 3, benchmark_id: 20, created_at: "2026-06-11T11:00:00Z" }),
    ]);
    expect(trend.points).toHaveLength(1);
    expect(trend.points[0].label).toBe("06-11");
  });

  it("computeRunsListKpis uses the same weighted daily latest benchmark pass rate", () => {
    const kpis = computeRunsListKpis([
      run({ id: 1, benchmark_id: 10, total: 100, passed: 80, created_at: "2026-06-10T09:00:00Z" }),
      run({ id: 2, benchmark_id: 10, total: 100, passed: 90, created_at: "2026-06-10T11:00:00Z" }),
      run({ id: 3, benchmark_id: 20, total: 50, passed: 40, created_at: "2026-06-10T12:00:00Z" }),
    ]);
    expect(kpis.avgPassPct).toBe(86.7);
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
    expect(trend.points).toHaveLength(2);
    expect(trend.points).toContainEqual(
      expect.objectContaining({
        label: "06-11",
        benchmark_10: 6,
        benchmark_10__p0: 2,
        benchmark_20: 12,
        benchmark_20__p0: 4,
      })
    );
    expect(trend.dateTicks).toHaveLength(2);
    expect(trend.xDomain).toEqual([
      new Date("2026-06-10T00:00:00").getTime(),
      new Date("2026-06-11T23:59:59.999").getTime(),
    ]);
    expect(trend.latestTotal).toBe(18);
    expect(trend.latestP0Total).toBe(6);
    expect(trend.previousTotal).toBe(14);
    expect(trend.previousP0Total).toBe(4);
    expect(trend.p0Delta).toBe(2);
    expect(trend.delta).toBe(4);
  });

  it("keeps only the latest evaluation per benchmark on each date", () => {
    const trend = buildCxAgentOptimizationTrend([
      run({ id: 1, benchmark_id: 10, benchmark_name: "真实患者", created_at: "2026-06-10T09:00:00Z", cx_agent_optimization_count: 3, cx_agent_p0_optimization_count: 1 }),
      run({ id: 2, benchmark_id: 10, benchmark_name: "真实患者", created_at: "2026-06-10T11:00:00Z", cx_agent_optimization_count: 5, cx_agent_p0_optimization_count: 2 }),
      run({ id: 3, benchmark_id: 20, benchmark_name: "合成对话", created_at: "2026-06-10T10:00:00Z", cx_agent_optimization_count: 7, cx_agent_p0_optimization_count: 3 }),
      run({ id: 4, benchmark_id: 20, benchmark_name: "合成对话", created_at: "2026-06-10T12:00:00Z", cx_agent_optimization_count: 11, cx_agent_p0_optimization_count: 4 }),
      run({ id: 5, benchmark_id: 10, benchmark_name: "真实患者", created_at: "2026-06-11T10:00:00Z", cx_agent_optimization_count: 6, cx_agent_p0_optimization_count: 2 }),
      run({ id: 6, benchmark_id: 20, benchmark_name: "合成对话", created_at: "2026-06-11T10:00:00Z", cx_agent_optimization_count: 12, cx_agent_p0_optimization_count: 5 }),
    ]);
    expect(trend.points).toHaveLength(2);
    expect(trend.points[0]).toEqual(expect.objectContaining({ benchmark_10: 5, benchmark_20: 11 }));
    expect(trend.latestTotal).toBe(18);
    expect(trend.latestP0Total).toBe(7);
    expect(trend.previousTotal).toBe(16);
    expect(trend.previousP0Total).toBe(6);
    expect(trend.p0Delta).toBe(1);
    expect(trend.delta).toBe(2);
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
    expect(trend.previousP0Total).toBeNull();
    expect(trend.p0Delta).toBeNull();
    expect(trend.delta).toBeNull();
  });

  it("computeRunsPeriodDeltas compares two windows", () => {
    const current = [
      run({
        id: 1, benchmark_id: 10, total: 100, passed: 90,
        created_at: "2026-06-11T10:00:00Z", medical_safety_failed: 1, avg_composite: 36,
      }),
      run({
        id: 2, benchmark_id: 20, total: 100, passed: 70,
        created_at: "2026-06-11T11:00:00Z", medical_safety_failed: 0, avg_composite: 30,
      }),
    ];
    const previous = [
      run({
        id: 3, benchmark_id: 10, total: 100, passed: 60,
        created_at: "2026-06-10T10:00:00Z", medical_safety_failed: 2, avg_composite: 27,
      }),
      run({
        id: 4, benchmark_id: 20, total: 100, passed: 60,
        created_at: "2026-06-10T11:00:00Z", medical_safety_failed: 0, avg_composite: 27,
      }),
    ];
    expect(computeRunsPeriodDeltas(current, previous)).toEqual({
      total: 0,
      passRatePct: 20,
      avgComposite: 6,
      medicalSafetyFailed: -1,
    });
  });

  it("compares cx-agent optimization points by the selected period and its previous period", () => {
    const current = [
      run({ id: 1, benchmark_id: 10, created_at: "2026-06-11T10:00:00Z", cx_agent_optimization_count: 5, cx_agent_p0_optimization_count: 2 }),
      run({ id: 2, benchmark_id: 10, created_at: "2026-06-11T11:00:00Z", cx_agent_optimization_count: 6, cx_agent_p0_optimization_count: 2 }),
      run({ id: 3, benchmark_id: 20, created_at: "2026-06-11T10:00:00Z", cx_agent_optimization_count: 12, cx_agent_p0_optimization_count: 4 }),
    ];
    const previous = [
      run({ id: 4, benchmark_id: 10, created_at: "2026-06-10T10:00:00Z", cx_agent_optimization_count: 4, cx_agent_p0_optimization_count: 1 }),
      run({ id: 5, benchmark_id: 20, created_at: "2026-06-10T10:00:00Z", cx_agent_optimization_count: 10, cx_agent_p0_optimization_count: 3 }),
    ];

    expect(computeCxAgentOptimizationPeriodDeltas(current, previous)).toEqual({ total: 4, p0Total: 2 });
  });

  it("does not compare cx-agent optimization points when a benchmark is missing in either period", () => {
    const current = [
      run({ id: 1, benchmark_id: 10, created_at: "2026-06-11T10:00:00Z", cx_agent_optimization_count: 6 }),
      run({ id: 2, benchmark_id: 20, created_at: "2026-06-11T10:00:00Z", cx_agent_optimization_count: 12 }),
    ];
    const previous = [
      run({ id: 3, benchmark_id: 10, created_at: "2026-06-10T10:00:00Z", cx_agent_optimization_count: 4 }),
    ];

    expect(computeCxAgentOptimizationPeriodDeltas(current, previous)).toBeNull();
  });

  it("does not compare pass rates when one period lacks a benchmark", () => {
    const current = [
      run({ id: 1, benchmark_id: 10, created_at: "2026-06-11T10:00:00Z" }),
      run({ id: 2, benchmark_id: 20, created_at: "2026-06-11T11:00:00Z" }),
    ];
    const previous = [
      run({ id: 3, benchmark_id: 10, created_at: "2026-06-10T10:00:00Z" }),
    ];
    expect(computeRunsPeriodDeltas(current, previous)?.passRatePct).toBeNull();
  });
});
