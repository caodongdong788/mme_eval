import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useRunsList } from "./useRunsList";
import { api, type RunSummary } from "../api/index";

vi.mock("../api/index", () => ({
  api: {
    listRuns: vi.fn(),
    getProgress: vi.fn(),
    deleteRun: vi.fn(),
  },
}));

vi.mock("antd", () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

const run = (id: number): RunSummary =>
  ({
    id,
    run_slug: `run-${id}`,
    name: `run-${id}`,
    status: "success",
    adapter_type: "openai_compat",
    pass_rate: 0.9,
    passed: 9,
    total: 10,
    hard_gate_failed: 0,
    n_runs: 1,
    error_msg: "",
    has_traces: true,
    pinned: false,
  }) as RunSummary;

describe("useRunsList onDelete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.listRuns.mockResolvedValue([run(1), run(2)]);
    mockedApi.getProgress.mockResolvedValue({
      status: "running",
      progress: { percent: 0, done: 0, total: 0 },
    });
    mockedApi.deleteRun.mockResolvedValue(undefined);
  });

  it("removes run from list immediately after delete succeeds", async () => {
    const { result } = renderHook(() => useRunsList());
    await waitFor(() => expect(result.current.runs).toHaveLength(2));

    await act(async () => {
      await result.current.onDelete(1);
    });

    expect(mockedApi.deleteRun).toHaveBeenCalledWith(1);
    expect(result.current.runs.map((r) => r.id)).toEqual([2]);
  });

  it("ignores stale in-flight reload that completes after delete", async () => {
    let resolveStaleList: (v: ReturnType<typeof run>[]) => void;
    const staleList = new Promise<ReturnType<typeof run>[]>((resolve) => {
      resolveStaleList = resolve;
    });

    mockedApi.listRuns
      .mockResolvedValueOnce([run(1), run(2)]) // initial mount
      .mockImplementationOnce(() => staleList); // manual reload started before delete

    const { result } = renderHook(() => useRunsList());
    await waitFor(() => expect(result.current.runs).toHaveLength(2));

    await act(async () => {
      const reloadPromise = result.current.reload();
      const deletePromise = result.current.onDelete(1);
      resolveStaleList!([run(1), run(2)]);
      await Promise.all([reloadPromise, deletePromise]);
    });

    expect(result.current.runs.map((r) => r.id)).toEqual([2]);
  });
});
