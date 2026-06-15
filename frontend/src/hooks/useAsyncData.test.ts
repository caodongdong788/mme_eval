import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useAsyncData } from "./useAsyncData";

describe("useAsyncData", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads data and clears loading", async () => {
    const fetcher = vi.fn().mockResolvedValue([1, 2, 3]);
    const { result } = renderHook(() => useAsyncData(fetcher, []));

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual([1, 2, 3]);
    expect(result.current.error).toBeNull();
  });

  it("sets error on failure", async () => {
    const fetcher = vi.fn().mockRejectedValue({ response: { data: { detail: "boom" } } });
    const { result } = renderHook(() => useAsyncData(fetcher, [], "加载失败"));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe("boom");
  });

  it("reload refetches", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(["a"]).mockResolvedValueOnce(["b"]);
    const { result } = renderHook(() => useAsyncData(fetcher, []));

    await waitFor(() => expect(result.current.data).toEqual(["a"]));
    result.current.reload();
    await waitFor(() => expect(result.current.data).toEqual(["b"]));
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
