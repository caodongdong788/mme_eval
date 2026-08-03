import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, type PairwiseCaseVerdict, type PairwiseDetail } from "../api/index";
import { pairwiseRagFilterValue, usePairwiseDetail } from "./usePairwiseDetail";

vi.mock("../api/index", () => ({
  api: { getPairwise: vi.fn() },
}));

const mockedApi = vi.mocked(api);

function verdict(
  sampleId: string,
  ragStatusA: PairwiseCaseVerdict["rag_status_a"],
  ragStatusB: PairwiseCaseVerdict["rag_status_b"]
): PairwiseCaseVerdict {
  return {
    sample_id: sampleId,
    rag_status_a: ragStatusA,
    rag_status_b: ragStatusB,
    winner: "tie",
    confidence_kind: "high",
    human_calibrated: false,
    swap_consistent: true,
    dimension_winners: {},
    reason: "",
  };
}

const verdicts = [
  verdict("hit", "not_triggered", "hit"),
  verdict("failed", "failed", "not_triggered"),
  verdict("not-triggered", "not_triggered", "not_triggered"),
  verdict("unknown", "unknown", "not_triggered"),
];

describe("usePairwiseDetail RAG filter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.getPairwise.mockResolvedValue({
      id: 1,
      status: "done",
      verdicts,
      summary: {},
    } as PairwiseDetail);
  });

  it("groups actual tool-call statuses into triggered, not-triggered, and unknown", () => {
    expect(verdicts.map(pairwiseRagFilterValue)).toEqual([
      "triggered",
      "triggered",
      "not_triggered",
      "unknown",
    ]);
  });

  it("filters verdicts by actual RAG trigger and resets it", async () => {
    const { result } = renderHook(() => usePairwiseDetail(1));
    await waitFor(() => expect(result.current.filtered).toHaveLength(4));

    act(() => result.current.setRagFilter("triggered"));
    expect(result.current.filtered.map((item) => item.sample_id)).toEqual(["hit", "failed"]);
    expect(result.current.hasActiveFilters).toBe(true);

    act(() => result.current.resetFilters());
    expect(result.current.filtered).toHaveLength(4);
    expect(result.current.hasActiveFilters).toBe(false);
  });
});
