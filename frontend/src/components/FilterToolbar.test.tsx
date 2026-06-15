import { describe, expect, it, vi } from "vitest";
import { FilterToolbar } from "./FilterToolbar";
import { renderWithProviders } from "../test/renderWithProviders";

describe("FilterToolbar", () => {
  const baseProps = {
    filters: {},
    setFilters: vi.fn(),
    reviewFilter: undefined,
    setReviewFilter: vi.fn(),
    onlyPending: false,
    setOnlyPending: vi.fn(),
    queueIds: new Set<string>(),
    hasActiveFilters: false,
    resetFilters: vi.fn(),
  };

  it("matches snapshot with no active filters", () => {
    const { container } = renderWithProviders(<FilterToolbar {...baseProps} />);
    expect(container.firstChild).toMatchSnapshot();
  });

  it("matches snapshot with active filters and pending queue", () => {
    const { container } = renderWithProviders(
      <FilterToolbar
        {...baseProps}
        filters={{ level: "L2", release_passed: "true" }}
        reviewFilter="agree"
        onlyPending
        queueIds={new Set(["case-1", "case-2"])}
        hasActiveFilters
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
