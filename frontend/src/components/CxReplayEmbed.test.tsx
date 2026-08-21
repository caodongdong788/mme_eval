import { act, cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "../test/renderWithProviders";
import { CxReplayEmbed } from "./CxReplayEmbed";

const props = {
  src: "https://cx.example.com/s/evaluation-token",
  messages: [{ role: "assistant", content: "已保存的本地回放" }],
};

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("CxReplayEmbed", () => {
  it("shows the saved conversation directly when no CX replay URL exists", () => {
    renderWithProviders(<CxReplayEmbed src={null} messages={props.messages} />);

    expect(screen.getByText("已保存的本地回放")).toBeInTheDocument();
    expect(screen.queryByText("CX 原生回放暂不可嵌入，已切换为本地回放")).not.toBeInTheDocument();
    expect(screen.queryByTitle("CX 完整回放")).not.toBeInTheDocument();
  });

  it("falls back to the saved conversation when CX does not confirm iframe readiness", () => {
    vi.useFakeTimers();
    renderWithProviders(<CxReplayEmbed {...props} />);

    act(() => vi.advanceTimersByTime(4_000));

    expect(screen.getByText("CX 原生回放暂不可嵌入，已切换为本地回放")).toBeInTheDocument();
    expect(screen.getByText("已保存的本地回放")).toBeInTheDocument();
  });

  it("keeps the native iframe when CX confirms readiness from the expected origin", () => {
    vi.useFakeTimers();
    renderWithProviders(<CxReplayEmbed {...props} />);

    act(() => {
      const readyEvent = new MessageEvent("message", {
        data: { source: "cx-agent", type: "cx-evaluation-replay-ready" },
      });
      Object.defineProperty(readyEvent, "origin", { value: "https://cx.example.com" });
      window.dispatchEvent(readyEvent);
      vi.advanceTimersByTime(4_000);
    });

    expect(screen.queryByText("CX 原生回放暂不可嵌入，已切换为本地回放")).not.toBeInTheDocument();
    expect(screen.getByTitle("CX 完整回放")).toBeInTheDocument();
  });
});
