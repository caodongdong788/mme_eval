import { cleanup, fireEvent, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, type AttributionTask, type CaseAttribution } from "../api/index";
import { clearConfigLabelMapCache } from "../hooks/useConfigLabelMap";
import { renderWithProviders } from "../test/renderWithProviders";
import { AttributionDetail, RunAttributionTab } from "./RunAttributionTab";

vi.mock("../api/index", () => ({
  api: {
    getAttributionTaskResult: vi.fn(),
    getAttributionTask: vi.fn(),
    listAttributionTasks: vi.fn(),
    createAttributionTask: vi.fn(),
    listJudgeModels: vi.fn(),
    rerunAttributionTask: vi.fn(),
    resumeAttributionTask: vi.fn(),
    deleteAttributionTask: vi.fn(),
    getJudgeVerdictLabels: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

afterEach(cleanup);

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
    validation_counts: { supported: 1, questionable: 3, insufficient_evidence: 1 },
    clusters: [
      {
        category: "cx_agent_issue",
        cause_code: "rag_not_grounded",
        cause_label: "召回证据未用于回答",
        owner: "generator",
        optimization_classification: {
          category_primary: "RAG 优化",
          category_secondary: "已召回但未使用",
          domain: "medical_rag",
          component: "rag_grounding",
          failure_mode: "rag_not_grounded",
          action_type: "grounding_rule",
          evidence_status: "sufficient",
          coverage_status: "mapped",
        },
        sample_ids: ["case_11"],
        deduction_ids: ["guideline.g01"],
        dimensions: ["medical_safety"],
        case_count: 1,
        deduction_count: 1,
        priority: "P0",
        confidence: 0.9,
        summary: "相关医学风险已经召回，但回答没有采用。",
        examples: ["相关医学风险已经召回，但回答没有采用。"],
        recommendations: [
          {
            priority: "P0",
            target: "回答生成",
            action: "生成回答前检查高风险医学证据是否已经覆盖。",
            verification: "使用当前用例和同类安全用例回归。",
            acceptance_criteria: "相关安全指南不再遗漏。",
          },
        ],
        verification_plan: {
          target_cases: ["case_11"],
          control_cases: [],
          safety_checks: ["不得降低医学安全性"],
          acceptance_criteria: ["相关安全指南不再遗漏"],
        },
      },
      {
        category: "evaluation_review",
        evaluation_issue_category: "judge_logic_issue",
        cause_code: "judge_context_missing",
        cause_label: "判分上下文需要复核",
        owner: "judge",
        sample_ids: ["case_11"],
        deduction_ids: ["guideline.g02"],
        dimensions: ["professional_accuracy"],
        case_count: 1,
        deduction_count: 1,
        priority: "P1",
        confidence: 0.8,
        summary: "判分前缺少完整上下文。",
        examples: ["判分前缺少完整上下文。"],
        recommendations: [],
        verification_plan: {
          target_cases: ["case_11"],
          control_cases: [],
          safety_checks: [],
          acceptance_criteria: [],
        },
      },
      {
        category: "evaluation_review",
        evaluation_issue_category: "benchmark_criteria_conflict",
        cause_code: "judge_or_benchmark_issue",
        cause_label: "判据与参考答案冲突",
        owner: "benchmark",
        sample_ids: ["case_11"],
        deduction_ids: ["guideline.g04"],
        dimensions: ["professional_accuracy"],
        case_count: 1,
        deduction_count: 1,
        priority: "P1",
        confidence: 0.9,
        summary: "同一行为在检查点中被禁止、在推荐回答中又被允许。",
        examples: ["同一行为在检查点中被禁止、在推荐回答中又被允许。"],
        recommendations: [],
        verification_plan: {
          target_cases: ["case_11"],
          control_cases: [],
          safety_checks: [],
          acceptance_criteria: [],
        },
      },
      {
        category: "evaluation_review",
        evaluation_issue_category: "annotation_rag_conflict",
        cause_code: "judge_or_benchmark_issue",
        cause_label: "标注超出文献证据",
        owner: "benchmark",
        sample_ids: ["case_11"],
        deduction_ids: ["guideline.g05"],
        dimensions: ["professional_accuracy"],
        case_count: 1,
        deduction_count: 1,
        priority: "P1",
        confidence: 0.85,
        summary: "标注结论超出了实际 RAG 文献能支持的范围。",
        examples: ["标注结论超出了实际 RAG 文献能支持的范围。"],
        recommendations: [],
        verification_plan: {
          target_cases: ["case_11"],
          control_cases: [],
          safety_checks: [],
          acceptance_criteria: [],
        },
      },
      {
        category: "cx_agent_issue",
        evaluation_issue_category: "missing_rag_reference",
        cause_code: "trace_missing",
        cause_label: "调用链证据缺失",
        owner: "unknown",
        optimization_classification: {
          category_primary: "RAG 优化",
          category_secondary: "缺少 RAG 引用",
          domain: "medical_rag",
          component: "citation_binding",
          failure_mode: "missing_rag_reference",
          action_type: "citation_binding",
          evidence_status: "insufficient",
          coverage_status: "mapped",
        },
        sample_ids: ["case_11"],
        deduction_ids: ["guideline.g03"],
        dimensions: [],
        case_count: 1,
        deduction_count: 1,
        priority: "P2",
        confidence: 0.4,
        summary: "缺少调用链记录，无法确认责任。",
        examples: ["缺少调用链记录，无法确认责任。"],
        recommendations: [],
        verification_plan: {
          target_cases: ["case_11"],
          control_cases: [],
          safety_checks: [],
          acceptance_criteria: [],
        },
      },
    ],
  },
  items: [
    {
      sample_id: "case_11",
      scenario: "骨质管理",
      case_type: "治疗方案与疗程决策",
      status: "success",
      error_msg: "",
      attribution_available: true,
      attribution_stale: false,
    },
  ],
};

describe("RunAttributionTab", () => {
  beforeEach(() => {
    clearConfigLabelMapCache();
    mockedApi.getJudgeVerdictLabels.mockResolvedValue({});
    mockedApi.listJudgeModels.mockResolvedValue([
      {
        id: 1,
        name: "kimi-k2.6",
        provider: "openai",
        model: "kimi-k2.6",
        base_url: "https://example.test/v1",
        api_version: "",
        pairwise_concurrency: 4,
        has_api_key: true,
      },
      {
        id: 2,
        name: "qwen3.8-max",
        provider: "openai",
        model: "qwen3.8-max",
        base_url: "https://example.test/v1",
        api_version: "",
        pairwise_concurrency: 4,
        has_api_key: true,
      },
    ]);
    mockedApi.listAttributionTasks.mockResolvedValue([{ ...task, items: [] }]);
    mockedApi.getAttributionTask.mockResolvedValue(task);
  });

  it("shows only the attribution task list by default", async () => {
    renderWithProviders(
      <MemoryRouter>
        <RunAttributionTab runId={26} />
      </MemoryRouter>
    );

    expect(await screen.findByText("归因任务 #99")).toBeInTheDocument();
    expect(screen.queryByText("归因任务总结")).not.toBeInTheDocument();
    expect(
      screen.queryByText("任务 #99 · 用例归因结果")
    ).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /查看明细/ })).toHaveAttribute(
      "href",
      "/runs/26/attribution-tasks/99"
    );
  });

  it("keeps the highest recommendation priority and shows traceable original evidence", async () => {
    const attributionResult: CaseAttribution = {
      available: true,
      stale: false,
      metadata: { model: "test-model", generated_at: "2026-08-18T10:00:00Z" },
      analysis: {
        analysis_status: "complete",
        score_health: { status: "healthy", summary: "判分结构完整", issues: [] },
        overall: {
          primary_cause_code: "context_not_used",
          primary_cause_label: "上下文未使用",
          owner: "context_timeline",
          confidence: 0.9,
          summary: "Timeline 事实未进入结论",
          affected_deduction_ids: ["dimension.professional_accuracy"],
        },
        rag_overview: {
          needed: false,
          enabled: false,
          actually_called: false,
          call_count: 0,
          diagnosis: "not_needed",
          summary: "本项不依赖 RAG",
        },
        deduction_analyses: [
          {
            deduction_id: "dimension.professional_accuracy",
            dimension: "professional_accuracy",
            deduction_validation: "supported",
            severity: "high",
            issue_type: "missing_information",
            required_information: ["patient_context"],
            finding: "已注入 Timeline 中“化疗后第 3 天持续腹泻”未用于判断就医时效。",
            evidence_summary: "Timeline 第 3 条记录为“化疗后第 3 天持续腹泻”。",
            impact: "遗漏持续时间使回答低估就医紧迫性并触发扣分。",
            observed_gap: {
              expected: "结合持续时间判断时效",
              actual: "回答仅建议等待下次复诊",
              gap: "未判断紧迫性",
              direct_evidence: [
                "Timeline 第 3 条记录为“化疗后第 3 天持续腹泻”。",
                "回答原文：可以等下次常规复诊时再咨询医生。",
              ],
            },
            causal_chain: [],
            primary_cause: {
              code: "context_not_used",
              label: "上下文已注入但未使用",
              owner: "context_timeline",
              confidence: 0.9,
              evidence_refs: ["case:timeline:3", "message:2"],
            },
            optimization_classification: {
              category_primary: "Agent 工程链路",
              category_secondary: "上下文已注入但未使用",
              domain: "context_memory",
              component: "context_usage",
              failure_mode: "context_not_used",
              action_type: "context_injection",
              evidence_status: "sufficient",
              coverage_status: "mapped",
            },
            contributing_causes: [],
            rag_diagnosis: {
              needed: false,
              called: false,
              query_quality: "unknown",
              relevant_information_stage: "unknown",
              answer_usage: "unknown",
              finding: "本项不依赖 RAG",
            },
            recommendations: [
              { priority: "P2", target: "普通检查", action: "增加输出检查" },
              { priority: "P0", target: "安全策略", action: "持续症状必须先完成就医时效判断" },
            ],
          },
        ],
        global_recommendations: [],
        limitations: [],
      },
    };
    renderWithProviders(
      <MemoryRouter>
        <AttributionDetail result={attributionResult} />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: "cx-agent 优化建议展开" }));
    fireEvent.click(screen.getByText("专业准确性与边界"));
    expect(screen.getByText("P0 · 最高优先级")).toBeInTheDocument();
    fireEvent.click(screen.getByText("问题分类：Agent 工程链路 / 上下文已注入但未使用"));
    expect(
      screen.getByText("原文：回答原文：可以等下次常规复诊时再咨询医生。")
    ).toBeInTheDocument();
    expect(screen.getByText("Timeline 长期事实")).toBeInTheDocument();
    expect(screen.getByText("当前对话")).toBeInTheDocument();
    expect(screen.queryByText(/Timeline 长期事实 · 3/)).not.toBeInTheDocument();
    expect(screen.queryByText(/对话消息 2/)).not.toBeInTheDocument();
  });

  it("shows a newly created attribution task immediately without a page refresh", async () => {
    const latestTask: AttributionTask = {
      ...task,
      id: 100,
      status: "running",
      completed_count: 0,
      success_count: 0,
      running_count: 1,
      pending_count: 0,
      items: [],
    };
    const view = renderWithProviders(
      <MemoryRouter>
        <RunAttributionTab runId={26} />
      </MemoryRouter>
    );

    expect(await screen.findByText("归因任务 #99")).toBeInTheDocument();
    view.rerender(
      <MemoryRouter>
        <RunAttributionTab runId={26} latestTask={latestTask} />
      </MemoryRouter>
    );

    expect(await screen.findByText("归因任务 #100")).toBeInTheDocument();
    expect(screen.getByText("归因任务 #99")).toBeInTheDocument();
  });

  it("shows the task summary and completed case results on the detail page", async () => {
    const { container } = renderWithProviders(
      <MemoryRouter>
        <RunAttributionTab
          runId={26}
          mode="detail"
          selectedTaskId={99}
          onSelectedTaskIdChange={vi.fn()}
        />
      </MemoryRouter>
    );

    expect(
      await screen.findByText("任务 #99 · 用例归因结果")
    ).toBeInTheDocument();
    expect(screen.getByText("归因任务总结")).toBeInTheDocument();
    expect(screen.getByText("cx-agent 优化建议")).toBeInTheDocument();
    expect(screen.getByText("评测工具优化建议")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "cx-agent 优化建议展开" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "评测工具优化建议展开" })
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "cx-agent 优化建议展开" })
    );
    const priorityFilter = screen.getByRole("combobox", {
      name: "按问题等级筛选 cx-agent 优化点",
    });
    fireEvent.mouseDown(priorityFilter);
    expect(screen.getByRole("option", { name: "P0" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "P1" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "P2" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /最高优先级/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /较高优先级/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /一般优先级/ })).not.toBeInTheDocument();
    fireEvent.keyDown(priorityFilter, { key: "Escape" });
    fireEvent.click(
      screen.getByRole("button", { name: "评测工具优化建议展开" })
    );
    expect(
      screen.getByRole("heading", { name: "Benchmark 判据冲突" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "判分点与 RAG 证据冲突" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "其他判分复核" })
    ).toBeInTheDocument();
    // cx-agent 建议按八维、优先级、文档中的一级/二级分类和具体动作展开。
    fireEvent.click(screen.getAllByText("医学安全性")[0]);
    expect(screen.getByText("P0 · 最高优先级")).toBeInTheDocument();
    expect(
      screen.getByText("问题分类：RAG 优化 / 已召回但未使用")
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByText("问题分类：RAG 优化 / 已召回但未使用")
    );
    expect(screen.getByText("通用问题描述：")).toBeInTheDocument();
    expect(screen.getByText("相关医学风险已经召回，但回答没有采用。")).toBeInTheDocument();
    expect(screen.getByText("怎么优化：")).toBeInTheDocument();
    expect(screen.getByText("关联 Case：")).toBeInTheDocument();
    const numberedPoints = container.querySelectorAll(
      ".attribution-numbered-points"
    );
    expect(numberedPoints).toHaveLength(2);
    expect(numberedPoints[0].tagName).toBe("OL");
    expect(numberedPoints[1].tagName).toBe("OL");
    fireEvent.click(screen.getByText("尚未关联维度"));
    expect(screen.getByText("P2 · 一般优先级")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Benchmark 判据冲突展开" })
    );
    expect(screen.getByText("判据冲突点：")).toBeInTheDocument();
    const caseLinks = screen.getAllByRole("link", {
      name: "查看 case_11 归因",
    });
    expect(caseLinks.length).toBeGreaterThan(0);
    expect(caseLinks[0]).toHaveAttribute(
      "href",
      "/runs/26/attribution-tasks/99/cases/case_11"
    );
    expect(screen.getByRole("button", { name: "Benchmark 判据冲突收起" })).toBeInTheDocument();
    expect(screen.getAllByText("建议操作：").length).toBeGreaterThan(0);
    expect(screen.getAllByText("医学安全性").length).toBeGreaterThan(0);
    expect(
      screen.getByRole("button", { name: /重新归因/ })
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /全\s*选/ }));
    expect(screen.getByRole("button", { name: /重新归因（1）/ })).toBeEnabled();
    const viewLink = await screen.findByRole("link", { name: /查看归因/ });
    expect(viewLink).toHaveAttribute(
      "href",
      "/runs/26/attribution-tasks/99/cases/case_11"
    );
    expect(mockedApi.getAttributionTaskResult).not.toHaveBeenCalled();
  });

  it("hides empty evaluation-tool categories from the task summary", async () => {
    const summaryWithoutRagConflict: AttributionTask = {
      ...task,
      diagnostic_summary: {
        ...task.diagnostic_summary!,
        clusters: task.diagnostic_summary!.clusters.filter(
          (cluster) =>
            cluster.evaluation_issue_category !== "annotation_rag_conflict"
        ),
      },
    };
    mockedApi.getAttributionTask.mockResolvedValue(summaryWithoutRagConflict);
    mockedApi.listAttributionTasks.mockResolvedValue([
      { ...summaryWithoutRagConflict, items: [] },
    ]);

    renderWithProviders(
      <MemoryRouter>
        <RunAttributionTab runId={26} mode="detail" selectedTaskId={99} />
      </MemoryRouter>
    );

    await screen.findByText("归因任务总结");
    fireEvent.click(
      screen.getByRole("button", { name: "评测工具优化建议展开" })
    );
    expect(
      screen.getByRole("heading", { name: "Benchmark 判据冲突" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "其他判分复核" })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "判分点与 RAG 证据冲突" })
    ).not.toBeInTheDocument();
  });

  it("merges same-dimension, same-secondary-category suggestions and keeps Case links", async () => {
    const firstCluster = task.diagnostic_summary!.clusters[0];
    const groupedTask: AttributionTask = {
      ...task,
      diagnostic_summary: {
        ...task.diagnostic_summary!,
        available_results: 2,
        clusters: [
          firstCluster,
          {
            ...firstCluster,
            sample_ids: ["case_12"],
            deduction_ids: ["guideline.g06"],
            summary: "高风险证据已经召回，但终答仍未采用。",
          },
        ],
      },
    };
    mockedApi.getAttributionTask.mockResolvedValue(groupedTask);
    mockedApi.listAttributionTasks.mockResolvedValue([{ ...groupedTask, items: [] }]);

    renderWithProviders(
      <MemoryRouter>
        <RunAttributionTab runId={26} mode="detail" selectedTaskId={99} />
      </MemoryRouter>
    );

    await screen.findByText("归因任务总结");
    fireEvent.click(screen.getByRole("button", { name: "cx-agent 优化建议展开" }));
    fireEvent.click(screen.getByText("医学安全性"));
    expect(screen.getByText("问题分类：RAG 优化 / 已召回但未使用")).toBeInTheDocument();
    fireEvent.click(screen.getByText("问题分类：RAG 优化 / 已召回但未使用"));
    expect(screen.getByText("2 个 Case · 2 项问题")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看 case_11 归因" })).toHaveAttribute(
      "href",
      "/runs/26/attribution-tasks/99/cases/case_11"
    );
    expect(screen.getByRole("link", { name: "查看 case_12 归因" })).toHaveAttribute(
      "href",
      "/runs/26/attribution-tasks/99/cases/case_12"
    );
  });

  it("reruns selected cases inside the current attribution task", async () => {
    mockedApi.rerunAttributionTask.mockResolvedValue({
      ...task,
      status: "queued",
      completed_count: 0,
      success_count: 0,
      pending_count: 1,
      items: [
        {
          ...task.items[0],
          status: "pending",
          attempt_count: 1,
          attribution_available: false,
        },
      ],
    });
    renderWithProviders(
      <MemoryRouter>
        <RunAttributionTab runId={26} mode="detail" selectedTaskId={99} />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole("button", { name: /全\s*选/ }));
    fireEvent.click(screen.getByRole("button", { name: /重新归因（1）/ }));
    expect(await screen.findByText("归因分析模型")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "开始重试" }));

    await vi.waitFor(() =>
      expect(mockedApi.rerunAttributionTask).toHaveBeenCalledWith(
        26,
        99,
        ["case_11"],
        1
      )
    );
    expect(mockedApi.createAttributionTask).not.toHaveBeenCalled();
    expect(await screen.findByText("等待重试")).toBeInTheDocument();
  });

  it("keeps task details visible while progress polling runs in the background", async () => {
    const runningTask: AttributionTask = {
      ...task,
      status: "running",
      completed_count: 0,
      success_count: 0,
      running_count: 1,
      pending_count: 0,
      items: [
        {
          ...task.items[0],
          status: "running",
          attribution_available: false,
        },
      ],
    };
    mockedApi.listAttributionTasks.mockResolvedValue([
      { ...runningTask, items: [] },
    ]);
    mockedApi.getAttributionTask
      .mockResolvedValueOnce(runningTask)
      .mockImplementation(() => new Promise(() => undefined));

    const { container } = renderWithProviders(
      <MemoryRouter>
        <RunAttributionTab
          runId={26}
          mode="detail"
          selectedTaskId={99}
          onSelectedTaskIdChange={vi.fn()}
        />
      </MemoryRouter>
    );

    expect(
      await screen.findByText("任务 #99 · 用例归因结果")
    ).toBeInTheDocument();
    expect(await screen.findByText(/分析中 1/)).toBeInTheDocument();
    // 正在分析只表示已开始，不得提前记入整体完成率。
    expect(await screen.findByText("0%")).toBeInTheDocument();
    await new Promise((resolve) => window.setTimeout(resolve, 1650));
    expect(
      mockedApi.getAttributionTask.mock.calls.length
    ).toBeGreaterThanOrEqual(2);
    expect(container.textContent).toContain("任务 #99 · 用例归因结果");
    expect(
      container.querySelector(".attribution-loading")
    ).not.toBeInTheDocument();
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
      items: [
        {
          ...task.items[0],
          status: "failed",
          error_msg: "HTTPException: 502: AI 归因生成失败：BadRequestError",
          attribution_available: false,
        },
      ],
    };
    mockedApi.listAttributionTasks.mockResolvedValue([
      { ...failedTask, items: [] },
    ]);
    mockedApi.getAttributionTask.mockResolvedValue(failedTask);

    renderWithProviders(
      <MemoryRouter>
        <RunAttributionTab
          runId={26}
          mode="detail"
          selectedTaskId={99}
          onSelectedTaskIdChange={vi.fn()}
        />
      </MemoryRouter>
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "查看失败原因" })
    );
    expect(
      await screen.findByText("当时的 Kimi K3 请求参数不兼容")
    ).toBeInTheDocument();
    expect(
      screen.getByText(/当前已按 Kimi K3 默认要求启用思考模式/)
    ).toBeInTheDocument();
    expect(
      screen.getByText("模型服务拒绝了本次请求，请检查模型参数与输入长度后重试")
    ).toBeInTheDocument();
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
    mockedApi.listAttributionTasks.mockResolvedValue([
      { ...interruptedTask, items: [] },
    ]);
    mockedApi.getAttributionTask.mockResolvedValue(interruptedTask);

    renderWithProviders(
      <MemoryRouter>
        <RunAttributionTab runId={26} />
      </MemoryRouter>
    );

    await screen.findByText("部分完成");
    expect(
      screen.getAllByRole("button").map((button) => button.textContent)
    ).toContain("继续归因");
  });

});
