import { cleanup, fireEvent, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, type AttributionTask, type CaseAttribution } from "../api";
import { clearConfigLabelMapCache } from "../hooks/useConfigLabelMap";
import { renderWithProviders } from "../test/renderWithProviders";
import AttributionCaseDetailPage from "./AttributionCaseDetailPage";

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
        recommendations: [],
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
    expect(screen.getByText("cx-agent问题归因")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "cx-agent问题归因展开" })
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "cx-agent问题归因展开" })
    );
    fireEvent.click(
      screen.getByRole("button", { name: "需要复核的判分展开" })
    );
    fireEvent.click(
      screen.getByRole("button", { name: "证据不足，暂不归责展开" })
    );
    // 单 Case 与任务汇总使用同一层级：八维 → 优化方向 → P0/P1/P2。
    fireEvent.click(screen.getByText("专业准确性与边界"));
    expect(screen.getByText("回答生成优化")).toBeInTheDocument();
    expect(screen.getByText("P1 · 较高优先级")).toBeInTheDocument();
    fireEvent.click(screen.getByText("回答在证据不足时给出了确定诊断"));
    expect(screen.getByText("评测要求与实际差距")).toBeInTheDocument();
    expect(screen.getByText("缺少不确定性说明和就医建议")).toBeInTheDocument();
    expect(screen.getByText("根因反事实检查")).toBeInTheDocument();
    expect(screen.getByText("优化建议")).toBeInTheDocument();
    expect(screen.getByText("提示词优化")).toBeInTheDocument();
    expect(screen.getByText("RAG 优化")).toBeInTheDocument();
    expect(screen.getByText("判分提示词优化")).toBeInTheDocument();
    expect(screen.getByText("判分上下文优化")).toBeInTheDocument();
    expect(screen.getByText("判分证据核验")).toBeInTheDocument();
    expect(screen.getByText("判分一致性优化")).toBeInTheDocument();
    expect(screen.queryByText("AI 助手优化建议")).not.toBeInTheDocument();
    expect(screen.queryByText("AI 助手提示词")).not.toBeInTheDocument();
    expect(screen.getByText("需要复核的判分")).toBeInTheDocument();
    expect(screen.getByText("证据不足，暂不归责")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "← 返回归因任务" }));
    expect(await screen.findByText("归因任务明细页")).toBeInTheDocument();
  });

  it("groups questionable deductions by the evaluation review source", async () => {
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

    expect(await screen.findByText("需要复核的判分")).toBeInTheDocument();
    const reviewExpand = screen.getByRole("button", {
      name: "需要复核的判分展开",
    });
    expect(reviewExpand).toBeInTheDocument();
    fireEvent.click(reviewExpand);
    expect(screen.getByText("Benchmark 判据冲突")).toBeInTheDocument();
    expect(screen.getByText("标注与 RAG 证据冲突")).toBeInTheDocument();
    expect(screen.getByText("其他判分复核")).toBeInTheDocument();
  });
});
