import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import { useCaseDetail } from "./useCaseDetail";

vi.mock("../api", () => ({
  api: {
    getCaseDetail: vi.fn(),
    getCaseAnnotations: vi.fn(),
    getRun: vi.fn(),
    listBenchmarks: vi.fn(),
    getNextCase: vi.fn(),
    getProgress: vi.fn(),
    retryCase: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

describe("useCaseDetail retry lifecycle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.getCaseDetail.mockResolvedValue({
      case: { sample_id: "case_55", scenario: "报告解读" },
      trace: {},
    });
    mockedApi.getCaseAnnotations.mockResolvedValue([]);
    mockedApi.getRun.mockResolvedValue({
      id: 19,
      status: "success",
      run_slug: "run-19",
    } as never);
    mockedApi.listBenchmarks.mockResolvedValue([]);
    mockedApi.getNextCase.mockResolvedValue({ sample_id: null });
    mockedApi.getProgress.mockResolvedValue({ status: "success", progress: null });
  });

  it("does not poll the old run status before retry submission is accepted", async () => {
    let acceptRetry: (() => void) | undefined;
    mockedApi.retryCase.mockImplementation(
      () => new Promise((resolve) => {
        acceptRetry = () => resolve({ id: 19, status: "pending" } as never);
      })
    );
    const { result } = renderHook(() => useCaseDetail(19, "case_55"));
    await waitFor(() => expect(mockedApi.getProgress).toHaveBeenCalledTimes(1));

    let retryRequest: Promise<void> | undefined;
    act(() => {
      retryRequest = result.current.retryCase();
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current.retrying).toBe(true);
    expect(mockedApi.getProgress).toHaveBeenCalledTimes(1);

    await act(async () => {
      acceptRetry?.();
      await retryRequest;
    });
    await waitFor(() => expect(mockedApi.getProgress).toHaveBeenCalledTimes(2));
  });

  it("restores polling when returning to the retry target case", async () => {
    mockedApi.getProgress.mockResolvedValue({
      status: "running",
      progress: {
        current_label: "调用 chatbot",
        done: 1,
        total: 4,
        percent: 25,
        context: { kind: "case_retry", sample_id: "case_55" },
      },
    });
    const { result } = renderHook(() => useCaseDetail(19, "case_55"));

    await waitFor(() => expect(result.current.retrying).toBe(true));
    expect(result.current.retryProgress?.progress?.percent).toBe(25);
  });
});
