import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import {
  clearPairwiseMessagesCache,
  usePairwiseExpandedMessages,
} from "./usePairwiseExpandedMessages";
import { api } from "../api/index";

vi.mock("../api/index", () => ({
  api: {
    getCaseDetail: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

describe("usePairwiseExpandedMessages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clearPairwiseMessagesCache();
    mockedApi.getCaseDetail.mockImplementation(async (runId: number) => ({
      trace: { messages: [{ role: "user", content: `run-${runId}` }] },
    }));
  });

  it("fetches both runs in parallel", async () => {
    const { result } = renderHook(() => usePairwiseExpandedMessages(1, 2, "bc_001"));

    await waitFor(() => expect(result.current.messagesA).toHaveLength(1));
    expect(result.current.messagesB).toHaveLength(1);
    expect(mockedApi.getCaseDetail).toHaveBeenCalledTimes(2);
    expect(mockedApi.getCaseDetail).toHaveBeenCalledWith(1, "bc_001");
    expect(mockedApi.getCaseDetail).toHaveBeenCalledWith(2, "bc_001");
  });

  it("uses cache on remount", async () => {
    renderHook(() => usePairwiseExpandedMessages(1, 2, "bc_001"));
    await waitFor(() => expect(mockedApi.getCaseDetail).toHaveBeenCalledTimes(2));

    vi.clearAllMocks();
    renderHook(() => usePairwiseExpandedMessages(1, 2, "bc_001"));
    await waitFor(() => expect(mockedApi.getCaseDetail).not.toHaveBeenCalled());
  });
});
