import { fireEvent, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, type AttributionTask, type CaseRow } from "../api/index";
import { clearConfigLabelMapCache } from "../hooks/useConfigLabelMap";
import { renderWithProviders } from "../test/renderWithProviders";
import { RunAttributionTab } from "./RunAttributionTab";

vi.mock("../api/index", () => ({
  api: {
    getAttributionTaskResult: vi.fn(),
    getAttributionTask: vi.fn(),
    listAttributionTasks: vi.fn(),
    createAttributionTask: vi.fn(),
    rerunAttributionTask: vi.fn(),
    resumeAttributionTask: vi.fn(),
    deleteAttributionTask: vi.fn(),
    getJudgeVerdictLabels: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

const failedCase: CaseRow = {
  id: 1,
  sample_id: "case_11",
  scenario: "骨质管理",
  case_type: "治疗方案与疗程决策",
  sub_scenario: "",
  level: "L2",
  medical_safety_passed: false,
  release_passed: false,
  grade: "不合格",
  stability: "稳挂",
  failure_tags: ["medical_safety_risk"],
};

const task: AttributionTask = {
  id: 99,
  run_id: 26,
  judge_model_id: 1,
  judge_model_name: "kimi-k2.6",
  status: "success",
  requested_count: 1,
  total_count: 1,
  skipped_count: 0,
  completed_count: 1,
  success_count: 1,
  failed_count: 0,
  running_count: 0,
  pending_count: 0,
  error_msg: "",
  diagnostic_summary: {
    available_results: 1,
    score_health_counts: { healthy: 1 },
    validation_counts: { supported: 1 },
    clusters: [{
      category: "cx_agent_issue",
      cause_code: "rag_not_grounded",
      cause_label: "召回证据未用于回答",
      owner: "generator",
      sample_ids: ["case_11"],
      deduction_ids: ["guideline.g01"],
      dimensions: ["medical_safety"],
      case_count: 1,
      deduction_count: 1,
      priority: "P0",
      confidence: 0.9,
      summary: "相关医学风险已经召回，但回答没有采用。",
      examples: ["相关医学风险已经召回，但回答没有采用。"],
      recommendations: [{
        priority: "P0",
        target: "回答生成",
        action: "生成回答前检查高风险医学证据是否已经覆盖。",
        verification: "使用当前用例和同类安全用例回归。",
        acceptance_criteria: "相关安全指南不再遗漏。",
      }],
      verification_plan: {
        target_cases: ["case_11"],
        control_cases: [],
        safety_checks: ["不得降低医学安全性"],
        acceptance_criteria: ["相关安全指南不再遗漏"],
      },
    }],
  },
  items: [{
    sample_id: "case_11",
    scenario: "骨质管理",
    case_type: "治疗方案与疗程决策",
    status: "success",
    error_msg: "",
    attribution_available: true,
    attribution_stale: false,
  }],
};

describe("RunAttributionTab", () => {
  beforeEach(() => {
    clearConfigLabelMapCache();
    mockedApi.getJudgeVerdictLabels.mockResolvedValue({});
    mockedApi.listAttributionTasks.mockResolvedValue([{ ...task, items: [] }]);
    mockedApi.getAttributionTask.mockResolvedValue(task);
  });

  it("shows a task and each completed case attribution immediately", async () => {
    renderWithProviders(
      <MemoryRouter>
        <RunAttributionTab
          runId={26}
          runStatus="success"
          cases={[failedCase]}
          selectedTaskId={99}
          onSelectedTaskIdChange={vi.fn()}
        />
      </MemoryRouter>
    );

    expect((await screen.findAllByText("归因任务 #99")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("归因进度").length).toBeGreaterThan(0);
    expect(screen.getByText("任务级问题诊断")).toBeInTheDocument();
    fireEvent.click(screen.getByText("召回证据未用于回答"));
    expect(screen.getByText("医学安全性")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /查看明细/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /重新归因/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "全选全部" }));
    expect(screen.getByRole("button", { name: /重新归因（1）/ })).toBeEnabled();
    expect(screen.getByRole("button", { name: /删除/ })).toBeInTheDocument();
    const viewLink = await screen.findByRole("link", { name: /查看归因/ });
    expect(viewLink).toHaveAttribute("href", "/runs/26/attribution-tasks/99/cases/case_11");
    expect(mockedApi.getAttributionTaskResult).not.toHaveBeenCalled();
  });

  it("keeps task details visible while progress polling runs in the background", async () => {
    const runningTask: AttributionTask = {
      ...task,
      status: "running",
      completed_count: 0,
      success_count: 0,
      running_count: 1,
      pending_count: 0,
      items: [{
        ...task.items[0],
        status: "running",
        attribution_available: false,
      }],
    };
    mockedApi.listAttributionTasks.mockResolvedValue([{ ...runningTask, items: [] }]);
    mockedApi.getAttributionTask
      .mockResolvedValueOnce(runningTask)
      .mockImplementation(() => new Promise(() => undefined));

    const { container } = renderWithProviders(
      <MemoryRouter>
        <RunAttributionTab
          runId={26}
          runStatus="success"
          cases={[failedCase]}
          selectedTaskId={99}
          onSelectedTaskIdChange={vi.fn()}
        />
      </MemoryRouter>
    );

    expect(await screen.findByText("任务 #99 · 用例归因结果")).toBeInTheDocument();
    expect(await screen.findByText(/分析中 1/)).toBeInTheDocument();
    await new Promise((resolve) => window.setTimeout(resolve, 1650));
    expect(mockedApi.getAttributionTask.mock.calls.length).toBeGreaterThanOrEqual(2);
    expect(container.textContent).toContain("任务 #99 · 用例归因结果");
    expect(container.querySelector(".attribution-loading")).not.toBeInTheDocument();
  });

  it("opens a useful failure-reason dialog", async () => {
    const failedTask: AttributionTask = {
      ...task,
      status: "failed",
      completed_count: 1,
      success_count: 0,
      failed_count: 1,
      running_count: 0,
      pending_count: 0,
      items: [{
        ...task.items[0],
        status: "failed",
        error_msg: "HTTPException: 502: AI 归因生成失败：BadRequestError",
        attribution_available: false,
      }],
    };
    mockedApi.listAttributionTasks.mockResolvedValue([{ ...failedTask, items: [] }]);
    mockedApi.getAttributionTask.mockResolvedValue(failedTask);

    renderWithProviders(
      <MemoryRouter>
        <RunAttributionTab
          runId={26}
          runStatus="success"
          cases={[failedCase]}
          selectedTaskId={99}
          onSelectedTaskIdChange={vi.fn()}
        />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole("button", { name: "查看失败原因" }));
    expect(await screen.findByText("当时的 Kimi K3 请求参数不兼容")).toBeInTheDocument();
    expect(screen.getByText(/当前已按 Kimi K3 默认要求启用思考模式/)).toBeInTheDocument();
    expect(screen.getByText("HTTPException: 502: AI 归因生成失败：BadRequestError")).toBeInTheDocument();
  });

  it("offers to continue an interrupted task without creating a new task", async () => {
    const interruptedTask: AttributionTask = {
      ...task,
      status: "partial",
      requested_count: 2,
      total_count: 2,
      completed_count: 1,
      success_count: 1,
      failed_count: 0,
      running_count: 0,
      pending_count: 0,
    };
    mockedApi.listAttributionTasks.mockResolvedValue([{ ...interruptedTask, items: [] }]);
    mockedApi.getAttributionTask.mockResolvedValue(interruptedTask);

    renderWithProviders(
      <MemoryRouter>
        <RunAttributionTab
          runId={26}
          runStatus="success"
          cases={[failedCase]}
          selectedTaskId={99}
          onSelectedTaskIdChange={vi.fn()}
        />
      </MemoryRouter>
    );

    await screen.findByText("部分完成");
    expect(screen.getAllByRole("button").map((button) => button.textContent)).toContain("继续归因");
  });
});
