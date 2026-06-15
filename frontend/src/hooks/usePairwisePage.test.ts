import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { usePairwisePage } from "./usePairwisePage";
import { api } from "../api/index";

vi.mock("../api/index", () => ({
  api: {
    listRuns: vi.fn(),
    listJudgeModels: vi.fn(),
    listPairwise: vi.fn(),
    precheckPairwise: vi.fn(),
    createPairwise: vi.fn(),
    updatePairwiseNote: vi.fn(),
    deletePairwise: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

describe("usePairwisePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.listRuns.mockResolvedValue([
      { id: 1, name: "run-a", status: "success", has_traces: true } as any,
      { id: 2, name: "run-b", status: "success", has_traces: true } as any,
    ]);
    mockedApi.listJudgeModels.mockResolvedValue([{ id: 10, name: "judge", model: "gpt" } as any]);
    mockedApi.listPairwise.mockResolvedValue([]);
    mockedApi.precheckPairwise.mockResolvedValue({
      comparable: true,
      reasons: [],
      subject_diff: {},
    });
  });

  it("loads runs and judge models on mount", async () => {
    const { result } = renderHook(() => usePairwisePage());
    await waitFor(() => expect(result.current.runs.length).toBe(2));
    expect(mockedApi.listRuns).toHaveBeenCalled();
    expect(mockedApi.listJudgeModels).toHaveBeenCalled();
    expect(result.current.judgeModels).toHaveLength(1);
  });

  it("prechecks when two distinct runs are selected", async () => {
    const { result } = renderHook(() => usePairwisePage());
    await waitFor(() => expect(result.current.runs.length).toBe(2));

    act(() => {
      result.current.setRunA(1);
      result.current.setRunB(2);
    });

    await waitFor(() => expect(mockedApi.precheckPairwise).toHaveBeenCalledWith(1, 2));
    expect(result.current.check?.comparable).toBe(true);
    expect(result.current.canSubmit).toBe(false);
  });

  it("canSubmit when runs, judge and comparability are set", async () => {
    const { result } = renderHook(() => usePairwisePage());
    await waitFor(() => expect(result.current.runs.length).toBe(2));

    act(() => {
      result.current.setRunA(1);
      result.current.setRunB(2);
      result.current.setJudgeId(10);
    });

    await waitFor(() => expect(result.current.canSubmit).toBe(true));
  });
});
