import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useYamlEditorState } from "./useYamlEditorState";
import { api } from "../api/index";

vi.mock("../api/index", () => ({
  api: {
    getRunCasesYaml: vi.fn(),
  },
}));

vi.mock("antd", () => ({
  message: { error: vi.fn() },
}));

const mockedApi = vi.mocked(api);

describe("useYamlEditorState", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.getRunCasesYaml.mockResolvedValue({ yaml_text: "cases:\n  - id: x" } as any);
  });

  it("opens editor and loads yaml from run", async () => {
    const { result } = renderHook(() => useYamlEditorState("my-run"));

    await act(async () => {
      await result.current.openFromRun(1, { sample_id: "bc_001" });
    });

    await waitFor(() => expect(result.current.yamlLoading).toBe(false));
    expect(mockedApi.getRunCasesYaml).toHaveBeenCalledWith(1, { sample_id: "bc_001" });
    expect(result.current.yamlOpen).toBe(true);
    expect(result.current.yamlText).toContain("cases:");
    expect(result.current.yamlName).toContain("my-run");
  });

  it("calls onBeforeOpen before fetch", async () => {
    const onBeforeOpen = vi.fn();
    const { result } = renderHook(() => useYamlEditorState());

    await act(async () => {
      await result.current.openFromRun(2, {}, { onBeforeOpen });
    });

    expect(onBeforeOpen).toHaveBeenCalled();
  });
});
