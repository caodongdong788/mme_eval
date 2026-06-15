import { describe, expect, it } from "vitest";
import { ConversationThread } from "./ConversationThread";
import { renderWithProviders } from "../test/renderWithProviders";

describe("ConversationThread", () => {
  it("matches snapshot for empty messages", () => {
    const { container } = renderWithProviders(<ConversationThread messages={[]} />);
    expect(container.firstChild).toMatchSnapshot();
  });

  it("matches snapshot for user/assistant/system messages", () => {
    const { container } = renderWithProviders(
      <ConversationThread
        messages={[
          { role: "user", content: "我最近胸口闷，需要去医院吗？" },
          { role: "assistant", content: "胸口闷可能由多种原因引起。\n请先观察是否伴有胸痛、呼吸困难。" },
          { role: "system", content: "internal note" },
        ]}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
