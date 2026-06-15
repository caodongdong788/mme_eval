import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { clearConfigLabelMapCache, useConfigLabelMap } from "./useConfigLabelMap";

describe("useConfigLabelMap", () => {
  beforeEach(() => {
    clearConfigLabelMapCache();
  });

  it("loads labels once and resolves via resolver", async () => {
    const fetcher = vi.fn().mockResolvedValue({ foo: "条" });
    const { result } = renderHook(() =>
      useConfigLabelMap("test-key", fetcher, (labels, key) => labels[key] || key)
    );

    expect(result.current("foo")).toBe("foo");
    await waitFor(() => expect(result.current("foo")).toBe("条"));
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("reuses cache across hook instances", async () => {
    const fetcher = vi.fn().mockResolvedValue({ a: "甲" });
    const { result, rerender } = renderHook(
      ({ fetcher: f }) =>
        useConfigLabelMap("shared", f, (labels, key) => labels[key] || key),
      { initialProps: { fetcher } }
    );
    await waitFor(() => expect(result.current("a")).toBe("甲"));

    rerender({ fetcher });
    await waitFor(() => expect(result.current("a")).toBe("甲"));
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
