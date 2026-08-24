import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, type RunAttributionCategoryStats, type RunSummary } from "../api";
import { useLatestAttributionCategoryStats } from "./useLatestAttributionCategoryStats";

vi.mock("../api", () => ({
  api: {
    getAttributionCategoryStats: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

function run(partial: Partial<RunSummary> & { id: number }): RunSummary {
  return {
    run_slug: `run_${partial.id}`,
    name: `run_${partial.id}`,
    status: "success",
    trigger_type: "manual",
    adapter_type: "openai_compat",
    total: 10,
    passed: 8,
    pass_rate: 0.8,
    medical_safety_failed: 0,
    n_runs: 1,
    error_msg: "",
    has_traces: true,
    pinned: false,
    evaluation_mode: "single_turn",
    ...partial,
  };
}

function stats(caseCount: number): RunAttributionCategoryStats {
  return {
    attributed_case_count: caseCount,
    first_level: [{ key: "prompt", label: "提示词", case_count: caseCount }],
    second_level: [],
  };
}

describe("useLatestAttributionCategoryStats", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not refetch when list polling returns new objects for the same latest run ids", async () => {
    mockedApi.getAttributionCategoryStats
      .mockResolvedValueOnce(stats(2))
      .mockResolvedValueOnce(stats(3));
    const selectedRuns = [
      run({ id: 10, benchmark_id: 1, cx_agent_optimization_count: 2, finished_at: "2026-08-24T01:00:00Z" }),
      run({ id: 20, benchmark_id: 2, cx_agent_optimization_count: 3, finished_at: "2026-08-24T02:00:00Z" }),
      run({ id: 99, status: "running", benchmark_id: 3, cx_agent_optimization_count: null }),
    ];
    const { result, rerender } = renderHook(
      ({ runs }) => useLatestAttributionCategoryStats(runs),
      { initialProps: { runs: selectedRuns } },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.stats?.attributed_case_count).toBe(5);
    expect(mockedApi.getAttributionCategoryStats).toHaveBeenCalledTimes(2);

    rerender({ runs: selectedRuns.map((item) => ({ ...item })) });
    await act(async () => Promise.resolve());

    expect(result.current.loading).toBe(false);
    expect(result.current.stats?.attributed_case_count).toBe(5);
    expect(mockedApi.getAttributionCategoryStats).toHaveBeenCalledTimes(2);
  });

  it("keeps current stats visible while a changed latest run is loading", async () => {
    let resolveUpdated!: (value: RunAttributionCategoryStats) => void;
    const updated = new Promise<RunAttributionCategoryStats>((resolve) => {
      resolveUpdated = resolve;
    });
    mockedApi.getAttributionCategoryStats
      .mockResolvedValueOnce(stats(2))
      .mockImplementationOnce(() => updated);
    const { result, rerender } = renderHook(
      ({ runs }) => useLatestAttributionCategoryStats(runs),
      {
        initialProps: {
          runs: [run({ id: 10, benchmark_id: 1, cx_agent_optimization_count: 2 })],
        },
      },
    );

    await waitFor(() => expect(result.current.stats?.attributed_case_count).toBe(2));
    rerender({
      runs: [run({ id: 11, benchmark_id: 1, cx_agent_optimization_count: 4 })],
    });

    await waitFor(() => expect(result.current.loading).toBe(true));
    expect(result.current.stats?.attributed_case_count).toBe(2);

    await act(async () => resolveUpdated(stats(4)));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.stats?.attributed_case_count).toBe(4);
  });
});
