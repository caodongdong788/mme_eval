import { describe, expect, it, vi } from "vitest";
import { HumanReviewCard } from "./HumanReviewCard";
import { renderWithProviders } from "../test/renderWithProviders";

describe("HumanReviewCard", () => {
  it("matches snapshot in agree mode", () => {
    const { container } = renderWithProviders(
      <HumanReviewCard
        verdict="agree"
        onVerdictChange={vi.fn()}
        suggestion=""
        onSuggestionChange={vi.fn()}
        comment=""
        onCommentChange={vi.fn()}
        saving={false}
        onSubmit={vi.fn()}
        onOpenEditor={vi.fn()}
        annotations={[]}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it("matches snapshot in override mode with history", () => {
    const { container } = renderWithProviders(
      <HumanReviewCard
        verdict="override"
        onVerdictChange={vi.fn()}
        suggestion="应建议急诊"
        onSuggestionChange={vi.fn()}
        comment="备注"
        onCommentChange={vi.fn()}
        saving={false}
        onSubmit={vi.fn()}
        onOpenEditor={vi.fn()}
        annotations={[
          {
            id: 1,
            verdict: "agree",
            reviewer: "alice",
            created_at: "2026-06-11T07:00:00",
          },
        ]}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
