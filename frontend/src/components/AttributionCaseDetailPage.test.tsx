import { cleanup, fireEvent, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, type AttributionTask, type CaseAttribution } from "../api";
import { clearConfigLabelMapCache } from "../hooks/useConfigLabelMap";
import { renderWithProviders } from "../test/renderWithProviders";
import AttributionCaseDetailPage from "../pages/AttributionCaseDetailPage";

afterEach(cleanup);

vi.mock("../api", () => ({
  api: {
    getAttributionTask: vi.fn(),
    getAttributionTaskResult: vi.fn(),
    getJudgeVerdictLabels: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

const task: AttributionTask = {
  id: 28,
  run_id: 26,
  judge_model_id: 3,
  judge_model_name: "kimi/kimi-k3",
  status: "running",
  requested_count: 22,
  total_count: 22,
  skipped_count: 0,
  completed_count: 1,
  success_count: 1,
  failed_count: 0,
  running_count: 3,
  pending_count: 18,
  error_msg: "",
  created_at: "2026-08-13T15:25:59+08:00",
  items: [
    {
      sample_id: "case_23",
      scenario: "报告解读",
      case_type: "检查报告与指标解读",
      status: "success",
      error_msg: "",
      attribution_available: true,
      attribution_stale: false,
    },
  ],
};

const result: CaseAttribution = {
  available: true,
  stale: false,
  metadata: {
    model: "kimi/kimi-k3",
    prompt_version: "case-attribution-v1",
    generated_at: "2026-08-13T15:32:27+08:00",
  },
  analysis: {
    analysis_status: "complete",
    overall: {
      primary_cause_code: "rag_not_grounded",
      primary_cause_label: "召回证据未被回答使用",
      owner: "generator",
      confidence: 0.91,
      summary: "RAG 已命中相关风险信息，但最终回答没有采用。",
      affected_deduction_ids: [],
    },
    rag_overview: {
      needed: true,
      needed_reason: "需要核对医学事实",
      enabled: true,
      actually_called: true,
      call_count: 1,
      diagnosis: "selected_not_used",
      summary: "召回正常，生成未引用。",
    },
    deduction_analyses: [
      {
        deduction_id: "guideline.g02_professional_accuracy",
        dimension: "professional_accuracy",
        deduction_validation: "supported",
        severity: "high",
        rubric_contract: {
          expected_behavior: ["说明结论边界并建议医生评估"],
          prohibited_behavior: ["在证据不足时下确定结论"],
          applicability: "当前回答给出了确定结论",
          scoring_rule: "遗漏边界说明扣 2 分",
          reference_answers: ["现有信息不足以确诊，建议进一步检查。"],
        },
        observed_gap: {
          expected: "说明结论边界并建议医生评估",
          actual: "回答直接给出了确定诊断",
          gap: "缺少不确定性说明和就医建议",
          direct_evidence: ["message:2"],
        },
        issue_type: "factual_error",
        required_information: ["reasoning"],
        finding: "回答在证据不足时给出了确定诊断",
        impact: "用户可能把尚未确认的判断当作最终诊断，延误进一步检查。",
        causal_chain: [
          {
            stage: "generation",
            status: "fail",
            finding: "最终回答没有表达不确定性",
            evidence_refs: ["message:2"],
          },
        ],
        primary_cause: {
          code: "response_composition_error",
          label: "回答生成缺少边界说明",
          owner: "generator",
          confidence: 0.9,
          reason: "生成阶段把可能性写成了确定结论",
          evidence_refs: ["message:2"],
        },
        optimization_classification: {
          category_primary: "提示词与回答生成策略",
          category_secondary: "行动步骤不清晰",
          domain: "response_delivery",
          component: "content_composition",
          failure_mode: "response_composition_error",
          action_type: "response_composition",
          evidence_status: "sufficient",
          coverage_status: "mapped",
        },
        root_cause_test: {
          if_fixed: "在生成阶段强制输出证据边界",
          would_prevent_issue: true,
          reason: "修复后不会再把可能性表述为确定诊断",
        },
        contributing_causes: [],
        rag_diagnosis: {
          needed: false,
          called: true,
          query_quality: "good",
          relevant_information_stage: "selected",
          answer_usage: "used",
          finding: "本项不是 RAG 问题",
        },
        recommendations: [
          {
            priority: "P1",
            target: "回答生成",
            action: "在生成确定性医学结论前检查证据是否足以支持诊断。",
          },
          {
            priority: "P1",
            target: "回答生成",
            action: "证据不足时明确说明判断边界并引导进一步检查。",
          },
        ],
      },
    ],
    global_recommendations: [
      {
        priority: "P0",
        target: "AI 助手提示词",
        action: "增加医学风险检查指令。",
        verification: "用风险用例回归。",
      },
      {
        priority: "P1",
        target: "agent_prompt",
        action: "增加回答前事实核对指令。",
        verification: "用事实性问题回归。",
      },
      {
        priority: "P1",
        target: "RAG 召回",
        action: "优化检索问题生成。",
        verification: "检查相关文献召回率。",
      },
      {
        priority: "P0",
        target: "判分模型提示词",
        action: "明确遗漏类扣分的适用规则。",
        verification: "用遗漏类用例回归。",
      },
      {
        priority: "P0",
        target: "判分模型",
        action: "将用户预置画像注入判分模型输入。",
        verification: "用含画像的用例回归。",
      },
      {
        priority: "P0",
        target: "判分模型",
        action: "扣分前全文检索关键词并引用原文证据。",
        verification: "抽样核对原文命中率。",
      },
      {
        priority: "P1",
        target: "判分模型",
        action: "扣分理由与评测判据逐条对齐，避免自相矛盾。",
        verification: "抽样检查判分一致性。",
      },
    ],
    limitations: [],
  },
};

describe("AttributionCaseDetailPage", () => {
  beforeEach(() => {
    clearConfigLabelMapCache();
    mockedApi.getJudgeVerdictLabels.mockResolvedValue({});
    mockedApi.getAttributionTask.mockResolvedValue(task);
    mockedApi.getAttributionTaskResult.mockResolvedValue(result);
  });

  it("opens as a separate result page and returns to the selected attribution task", async () => {
    renderWithProviders(
      <MemoryRouter
        initialEntries={["/runs/26/attribution-tasks/28/cases/case_23"]}
      >
        <Routes>
          <Route
            path="/runs/:runId/attribution-tasks/:taskId/cases/:sampleId"
            element={<AttributionCaseDetailPage />}
          />
          <Route
            path="/runs/:runId/attribution-tasks/:taskId"
            element={<div>归因任务明细页</div>}
          />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText("case_23 · 归因结果")).toBeInTheDocument();
    expect(screen.queryByText("医学知识检索（RAG）")).not.toBeInTheDocument();
    expect(screen.queryByText("医学安全性专项分析")).not.toBeInTheDocument();
    expect(screen.getByText("cx-agent 优化建议")).toBeInTheDocument();
    expect(screen.queryByText("评测工具优化建议")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "cx-agent 优化建议展开" })
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "cx-agent 优化建议展开" })
    );
    // 单 Case 与任务汇总使用同一层级：八维 → P0/P1/P2 → 问题 → 分类 → 怎么优化。
    fireEvent.click(screen.getByText("专业准确性与边界"));
    expect(screen.getByText("P1 · 较高优先级")).toBeInTheDocument();
    fireEvent.click(
      screen.getByText("问题分类：提示词与回答生成策略 / 行动步骤不清晰")
    );
    expect(screen.getByText("问题描述：")).toBeInTheDocument();
    expect(screen.getByText("导致问题：")).toBeInTheDocument();
    expect(
      screen.getByText("用户可能把尚未确认的判断当作最终诊断，延误进一步检查。")
    ).toBeInTheDocument();
    expect(screen.getByText("怎么优化：")).toBeInTheDocument();
    const optimizationList = screen.getByText("怎么优化：").parentElement?.querySelector("ol");
    expect(optimizationList).not.toBeNull();
    expect(optimizationList?.querySelectorAll("li")).toHaveLength(2);
    expect(optimizationList?.textContent).toContain(
      "在生成确定性医学结论前检查证据是否足以支持诊断。"
    );
    expect(optimizationList?.textContent).toContain(
      "证据不足时明确说明判断边界并引导进一步检查。"
    );
    expect(screen.queryByText("判分需要复核")).not.toBeInTheDocument();
    expect(screen.queryByText("需要复核的判分")).not.toBeInTheDocument();
    expect(screen.queryByText("待补充证据")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "← 返回归因任务" }));
    expect(await screen.findByText("归因任务明细页")).toBeInTheDocument();
  });

  it("shows pending evidence only when an evidence-insufficient deduction exists", async () => {
    const baseDeduction = result.analysis!.deduction_analyses[0];
    mockedApi.getAttributionTaskResult.mockResolvedValue({
      ...result,
      analysis: {
        ...result.analysis!,
        deduction_analyses: [{
          ...baseDeduction,
          deduction_validation: "insufficient_evidence",
          evaluation_issue_category: "evidence_gap",
          finding: "缺少最终生成上下文，无法确认相关文献是否提供给回答模型。",
          recommendations: [],
        }],
        global_recommendations: [],
        limitations: ["需要补充最终选中文献与最终生成上下文的映射记录。"],
      },
    });

    renderWithProviders(
      <MemoryRouter
        initialEntries={["/runs/26/attribution-tasks/28/cases/case_23"]}
      >
        <Routes>
          <Route
            path="/runs/:runId/attribution-tasks/:taskId/cases/:sampleId"
            element={<AttributionCaseDetailPage />}
          />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText("待补充证据")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "待补充证据展开" }));
    expect(screen.getByText("需要补充的证据")).toBeInTheDocument();
    expect(screen.queryByText("缺少的证据")).not.toBeInTheDocument();
    expect(screen.getByText("缺少最终生成上下文，无法确认相关文献是否提供给回答模型。")).toBeInTheDocument();
  });

  it("hides pending evidence when the API only returns empty limitation values", async () => {
    mockedApi.getAttributionTaskResult.mockResolvedValue({
      ...result,
      analysis: {
        ...result.analysis!,
        limitations: ["", "  "],
      },
    });

    renderWithProviders(
      <MemoryRouter
        initialEntries={["/runs/26/attribution-tasks/28/cases/case_23"]}
      >
        <Routes>
          <Route
            path="/runs/:runId/attribution-tasks/:taskId/cases/:sampleId"
            element={<AttributionCaseDetailPage />}
          />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText("cx-agent 优化建议")).toBeInTheDocument();
    expect(screen.queryByText("待补充证据")).not.toBeInTheDocument();
  });

  it("hides pending evidence when there are no evidence-insufficient deductions", async () => {
    mockedApi.getAttributionTaskResult.mockResolvedValue({
      ...result,
      analysis: {
        ...result.analysis!,
        limitations: ["缺少候选文献筛选记录，但当前没有待补证的扣分项。"],
      },
    });

    renderWithProviders(
      <MemoryRouter
        initialEntries={["/runs/26/attribution-tasks/28/cases/case_23"]}
      >
        <Routes>
          <Route
            path="/runs/:runId/attribution-tasks/:taskId/cases/:sampleId"
            element={<AttributionCaseDetailPage />}
          />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText("cx-agent 优化建议")).toBeInTheDocument();
    expect(screen.queryByText("待补充证据")).not.toBeInTheDocument();
  });

  it("shows evaluation-tool optimization for questionable deductions", async () => {
    const baseDeduction = result.analysis!.deduction_analyses[0];
    mockedApi.getAttributionTaskResult.mockResolvedValue({
      ...result,
      analysis: {
        ...result.analysis!,
        deduction_analyses: [
          baseDeduction,
          {
            ...baseDeduction,
            deduction_id: "guideline.g03_benchmark_conflict",
            deduction_validation: "questionable",
            evaluation_issue_category: "benchmark_criteria_conflict",
            finding: "检查点与推荐回答的适用条件冲突。",
          },
          {
            ...baseDeduction,
            deduction_id: "guideline.g04_annotation_rag_conflict",
            deduction_validation: "questionable",
            evaluation_issue_category: "annotation_rag_conflict",
            finding: "标注结论无法由当前 RAG 原文支持。",
          },
          {
            ...baseDeduction,
            deduction_id: "guideline.g05_judge_logic",
            deduction_validation: "questionable",
            evaluation_issue_category: "judge_logic_issue",
            finding: "判分可能遗漏了用户档案中的限定条件。",
          },
        ],
      },
    });

    renderWithProviders(
      <MemoryRouter
        initialEntries={["/runs/26/attribution-tasks/28/cases/case_23"]}
      >
        <Routes>
          <Route
            path="/runs/:runId/attribution-tasks/:taskId/cases/:sampleId"
            element={<AttributionCaseDetailPage />}
          />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText("cx-agent 优化建议")).toBeInTheDocument();
    expect(screen.getByText("评测工具优化建议")).toBeInTheDocument();
    expect(screen.queryByText("判分需要复核")).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "评测工具优化建议展开" })
    );
    expect(screen.getByText("Benchmark 判据冲突")).toBeInTheDocument();
    expect(screen.getByText("标注与 RAG 证据冲突")).toBeInTheDocument();
    expect(screen.getByText("其他判分复核")).toBeInTheDocument();
  });
});
