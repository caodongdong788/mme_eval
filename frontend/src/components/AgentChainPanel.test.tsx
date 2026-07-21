import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "../test/renderWithProviders";
import { AgentChainPanel } from "./AgentChainPanel";

describe("AgentChainPanel", () => {
  it("shows reset identity, blank profile and nested Langfuse observations", () => {
    const onSync = vi.fn();
    renderWithProviders(
      <AgentChainPanel
        onSync={onSync}
        trace={{
          langfuse_trace_ids: ["trace-1"],
          evaluation_identity: {
            test_user_id: "00000000-0000-0000-0000-000000000101",
            reset_status: "success",
            reset_at: "2026-07-21T08:00:00Z",
            profile_after_reset: {},
            user_profile: { nickname: null, medical: null },
          },
          agent_chain: {
            status: "synced",
            trace_ids: ["trace-1"],
            traces: [{ trace_id: "trace-1", trace_url: "https://lf.example/trace-1" }],
            nodes: [
              { id: "agent", trace_id: "trace-1", type: "AGENT", name: "agent-loop" },
              {
                id: "tool",
                trace_id: "trace-1",
                parent_id: "agent",
                type: "TOOL",
                name: "search-memory",
                output: { found: false },
              },
            ],
          },
        }}
      />
    );

    expect(screen.getByText("已清空")).toBeInTheDocument();
    expect(screen.getByText("空画像（本期基线评测）")).toBeInTheDocument();
    expect(screen.getByText("agent-loop")).toBeInTheDocument();
    expect(screen.getByText("search-memory")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /重新同步/ }));
    expect(onSync).toHaveBeenCalledOnce();
  });
});
