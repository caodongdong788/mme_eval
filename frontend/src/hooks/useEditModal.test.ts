import { describe, expect, it } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useEditModal } from "./useEditModal";

describe("useEditModal", () => {
  it("opens create mode with defaults", () => {
    const { result } = renderHook(() => useEditModal<number>());

    act(() => {
      result.current.openCreate({ name: "new" });
    });

    expect(result.current.open).toBe(true);
    expect(result.current.editId).toBeNull();
    expect(result.current.isEditing).toBe(false);
  });

  it("opens edit mode with id", () => {
    const { result } = renderHook(() => useEditModal<number>());

    act(() => {
      result.current.openEdit(42, { name: "existing" });
    });

    expect(result.current.open).toBe(true);
    expect(result.current.editId).toBe(42);
    expect(result.current.isEditing).toBe(true);
  });

  it("closes modal", () => {
    const { result } = renderHook(() => useEditModal<number>());

    act(() => {
      result.current.openCreate();
      result.current.close();
    });

    expect(result.current.open).toBe(false);
  });
});
