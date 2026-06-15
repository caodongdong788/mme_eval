import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { PairwiseConversationCol } from "./PairwiseConversationCol";
import { renderWithProviders } from "../test/renderWithProviders";

function renderCol(messages: { role: string; content: string }[]) {
  return renderWithProviders(
    <MemoryRouter>
      <PairwiseConversationCol
        messages={messages}
        side="A"
        runName="baseline-run"
        runId={1}
        sampleId="bc_001"
        comparisonId={9}
      />
    </MemoryRouter>
  );
}

describe("PairwiseConversationCol", () => {
  it("matches snapshot for empty messages", () => {
    const { container } = renderCol([]);
    expect(container.firstChild).toMatchSnapshot();
  });

  it("matches snapshot for user and assistant messages", () => {
    const { container } = renderCol([
      { role: "user", content: "我胸口闷" },
      { role: "assistant", content: "建议尽快就医评估。" },
    ]);
    expect(container.firstChild).toMatchSnapshot();
  });
});
