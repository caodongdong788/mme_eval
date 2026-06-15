import { describe, expect, it, vi } from "vitest";
import { RunDetail } from "../api";
import { RunDashboardHeader } from "./RunDashboardHeader";
import { renderWithProviders } from "../test/renderWithProviders";

const baseRun = {
  id: 1,
  name: "基准回归",
  run_slug: "run-1",
  status: "success",
  adapter_type: "http",
  total: 10,
  passed: 8,
  pass_rate: 0.8,
  hard_gate_failed: 0,
  n_runs: 3,
  error_msg: "",
  has_traces: true,
  pinned: false,
  judge_overrides: { model: "gpt-4" },
} as unknown as RunDetail;

describe("RunDashboardHeader", () => {
  it("matches snapshot", () => {
    const { container } = renderWithProviders(
      <RunDashboardHeader
        run={baseRun}
        editingName={false}
        nameDraft=""
        savingName={false}
        acting={false}
        onNameDraftChange={vi.fn()}
        onStartEditName={vi.fn()}
        onCommitName={vi.fn()}
        onRejudge={vi.fn()}
        onResume={vi.fn()}
        onTogglePin={vi.fn()}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
