import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/index";
import { useCaseDetail } from "./useCaseDetail";

vi.mock("../api/index", () => ({
  api: {
    getCaseDetail: vi.fn(),
    getCaseAnnotations: vi.fn(),
    getRun: vi.fn(),
    listBenchmarks: vi.fn(),
    getProgress: vi.fn(),
    getNextCase: vi.fn(),
    getBenchmarkCaseContent: vi.fn(),
    previewRejudgeCase: vi.fn(),
    saveBenchmarkCaseContent: vi.fn(),
    retryCase: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);
const structuredCase = {
  benchmark_id: 12,
  sample_id: "case_55",
  case_file: "cases.yaml",
  case: {
    sample_id: "case_55",
    scenario: "报告解读",
    evaluation: {
      dimension_criteria: { medical_safety: ["不得遗漏危险信号"] },
      guidelines: [],
    },
  },
};

describe("useCaseDetail structured criteria editor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.getCaseDetail.mockResolvedValue({ case: structuredCase.case, trace: {} });
    mockedApi.getCaseAnnotations.mockResolvedValue([]);
    mockedApi.getRun.mockResolvedValue({
      id: 19,
      name: "评测 19",
      benchmark_id: 12,
      status: "success",
    } as never);
    mockedApi.listBenchmarks.mockResolvedValue([
      { id: 12, name: "真实患者数据集benchmark", source: "uploaded" },
    ] as never);
    mockedApi.getProgress.mockResolvedValue({ status: "success", progress: null });
    mockedApi.getNextCase.mockResolvedValue({ sample_id: null });
    mockedApi.getBenchmarkCaseContent.mockResolvedValue(structuredCase);
    mockedApi.previewRejudgeCase.mockResolvedValue({ changed: false } as never);
    mockedApi.saveBenchmarkCaseContent.mockResolvedValue(structuredCase);
  });

  it("loads structured benchmark content and submits structured criteria", async () => {
    const { result } = renderHook(() => useCaseDetail(19, "case_55"));
    await waitFor(() => expect(result.current.run?.benchmark_id).toBe(12));

    await act(async () => {
      await result.current.openEditor();
    });
    expect(mockedApi.getBenchmarkCaseContent).toHaveBeenCalledWith(12, "case_55");
    expect(result.current.caseContent).toEqual(structuredCase);

    await act(async () => {
      await result.current.runPreview();
    });
    expect(mockedApi.previewRejudgeCase).toHaveBeenCalledWith(19, "case_55", {
      case_override: {
        sample_id: "case_55",
        evaluation: structuredCase.case.evaluation,
      },
    });

    await act(async () => {
      await result.current.saveCaseOverwrite();
    });
    expect(mockedApi.saveBenchmarkCaseContent).toHaveBeenCalledWith(
      12,
      "case_55",
      structuredCase.case
    );
  });
});

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
