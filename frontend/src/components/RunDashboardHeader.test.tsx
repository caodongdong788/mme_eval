import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { RunDetail } from "../api/index";
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
  medical_safety_failed: 0,
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

  it("hides run actions outside the overview tab", () => {
    renderWithProviders(
      <RunDashboardHeader
        run={baseRun}
        showActions={false}
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

    expect(screen.queryByRole("button", { name: "重判" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "续跑" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "置顶" })).not.toBeInTheDocument();
  });
});
