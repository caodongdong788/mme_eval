import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConversationThread } from "./ConversationThread";
import { renderWithProviders } from "../test/renderWithProviders";

describe("ConversationThread", () => {
  it("renders an empty thread", () => {
    const { container } = renderWithProviders(<ConversationThread messages={[]} />);
    expect(container.firstChild).toBeEmptyDOMElement();
  });

  it("renders assistant markdown and converts msg_break to a divider", () => {
    const { container } = renderWithProviders(
      <ConversationThread
        messages={[
          { role: "user", content: "我最近胸口闷，需要去医院吗？" },
          { role: "assistant", content: "**现在能做的是：**\n\n- 观察胸痛\n- 留意呼吸困难\n\n<msg_break />\n\n继续观察。" },
          { role: "system", content: "internal note" },
        ]}
      />
    );

    expect(screen.getByText("现在能做的是：").tagName).toBe("STRONG");
    expect(screen.getByText("观察胸痛").tagName).toBe("LI");
    expect(screen.getByText("留意呼吸困难").tagName).toBe("LI");
    expect(container.querySelector("hr")).toBeInTheDocument();
    expect(screen.queryByText(/msg_break/)).not.toBeInTheDocument();
    expect(screen.getByText("我最近胸口闷，需要去医院吗？")).toBeInTheDocument();
  });

  it("renders Case markdown images through the provided protected source", () => {
    renderWithProviders(
      <ConversationThread
        resolveImageSrc={(path) => `/api/runs/1/cases/case_1/images/${encodeURIComponent(path)}`}
        messages={[{ role: "user", content: "![报告图](images/report.jpg)" }]}
      />
    );

    expect(screen.getByTestId("case-conversation-image")).toHaveAttribute(
      "src",
      "/api/runs/1/cases/case_1/images/images%2Freport.jpg"
    );
  });
});
