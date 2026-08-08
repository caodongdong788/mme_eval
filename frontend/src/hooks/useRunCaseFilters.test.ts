import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, type CaseRow } from "../api/index";
import { useRunCaseFilters } from "./useRunCaseFilters";

vi.mock("../api/index", () => ({
  CASE_LIST_LIMIT: 100,
  api: {
    listCaseResults: vi.fn(),
    getReviewStats: vi.fn(),
    getReviewQueue: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);
const caseRow: CaseRow = {
  id: 1,
  sample_id: "case-1",
  scenario: "症状识别",
  case_type: "medical_consultation",
  sub_scenario: "",
  level: "L2",
  medical_safety_passed: true,
  release_passed: true,
  grade: "优秀",
  stability: "stable_pass",
  failure_tags: [],
};

describe("useRunCaseFilters live refresh", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    mockedApi.listCaseResults.mockResolvedValue([caseRow]);
    mockedApi.getReviewStats.mockResolvedValue({
      queue_total: 0,
      reviewed: 0,
      pending: 0,
      agree: 0,
      override: 0,
      agree_rate: 0,
      disagree_rate: 0,
    });
    mockedApi.getReviewQueue.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("polls cases while the run is active and stops after the final refresh", async () => {
    const { result, rerender } = renderHook(
      ({ status }) => useRunCaseFilters(18, (tag) => tag, true, status),
      { initialProps: { status: "running" } },
    );

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(mockedApi.listCaseResults).toHaveBeenCalledTimes(1);
    await act(async () => {
      vi.advanceTimersByTime(2000);
      await Promise.resolve();
    });
    expect(mockedApi.listCaseResults).toHaveBeenCalledTimes(2);
    expect(result.current.cases).toEqual([caseRow]);

    rerender({ status: "success" });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    const callsAfterFinalRefresh = mockedApi.listCaseResults.mock.calls.length;
    await act(async () => {
      vi.advanceTimersByTime(4000);
      await Promise.resolve();
    });
    expect(mockedApi.listCaseResults).toHaveBeenCalledTimes(callsAfterFinalRefresh);
  });
});
