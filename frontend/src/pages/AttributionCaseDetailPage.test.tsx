import { fireEvent, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, type AttributionTask, type CaseAttribution } from "../api";
import { clearConfigLabelMapCache } from "../hooks/useConfigLabelMap";
import { renderWithProviders } from "../test/renderWithProviders";
import AttributionCaseDetailPage from "./AttributionCaseDetailPage";

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
  items: [{
    sample_id: "case_23",
    scenario: "报告解读",
    case_type: "检查报告与指标解读",
    status: "success",
    error_msg: "",
    attribution_available: true,
    attribution_stale: false,
  }],
};

const result: CaseAttribution = {
  available: true,
  stale: false,
  metadata: { model: "kimi/kimi-k3", prompt_version: "case-attribution-v1", generated_at: "2026-08-13T15:32:27+08:00" },
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
    deduction_analyses: [],
    global_recommendations: [
      { priority: "P0", target: "AI 助手提示词", action: "增加医学风险检查指令。", verification: "用风险用例回归。" },
      { priority: "P1", target: "agent_prompt", action: "增加回答前事实核对指令。", verification: "用事实性问题回归。" },
      { priority: "P1", target: "RAG 召回", action: "优化检索问题生成。", verification: "检查相关文献召回率。" },
      { priority: "P0", target: "判分模型提示词", action: "明确遗漏类扣分的适用规则。", verification: "用遗漏类用例回归。" },
      { priority: "P0", target: "判分模型", action: "将用户预置画像注入判分模型输入。", verification: "用含画像的用例回归。" },
      { priority: "P0", target: "判分模型", action: "扣分前全文检索关键词并引用原文证据。", verification: "抽样核对原文命中率。" },
      { priority: "P1", target: "判分模型", action: "扣分理由与评测判据逐条对齐，避免自相矛盾。", verification: "抽样检查判分一致性。" },
    ],
    limitations: [],
  },
};

function ReturnProbe() {
  const location = useLocation();
  return <div data-testid="return-state">{JSON.stringify(location.state)}</div>;
}

describe("AttributionCaseDetailPage", () => {
  beforeEach(() => {
    clearConfigLabelMapCache();
    mockedApi.getJudgeVerdictLabels.mockResolvedValue({});
    mockedApi.getAttributionTask.mockResolvedValue(task);
    mockedApi.getAttributionTaskResult.mockResolvedValue(result);
  });

  it("opens as a separate result page and returns to the selected attribution task", async () => {
    renderWithProviders(
      <MemoryRouter initialEntries={["/runs/26/attribution-tasks/28/cases/case_23"]}>
        <Routes>
          <Route path="/runs/:runId/attribution-tasks/:taskId/cases/:sampleId" element={<AttributionCaseDetailPage />} />
          <Route path="/runs/:runId" element={<ReturnProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("case_23 · 归因结果")).toBeInTheDocument();
    expect(screen.queryByText("医学知识检索（RAG）")).not.toBeInTheDocument();
    expect(screen.queryByText("医学安全性专项分析")).not.toBeInTheDocument();
    expect(screen.getByText("cx-agent问题归因")).toBeInTheDocument();
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
    expect(await screen.findByTestId("return-state")).toHaveTextContent('"tab":"attribution"');
    expect(screen.getByTestId("return-state")).toHaveTextContent('"attributionTaskId":28');
  });
});
