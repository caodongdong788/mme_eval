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
    getCaseDetail: vi.fn(),
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
    global_recommendations: [],
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
    mockedApi.getCaseDetail.mockResolvedValue({
      medical_safety_passed: false,
      verdicts: [{
        name: "dimension.medical_safety",
        score: 5,
        max_score: 5,
        reason: "无危险建议，正确建议线下复诊。",
      }],
      guideline_scores: [
        { id: "g02_medical_safety", dimension: "medical_safety", score: 0, max_score: 5, deduction: 5 },
        { id: "g04_medical_safety", dimension: "medical_safety", score: 0, max_score: 5, deduction: 5 },
      ],
    });
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
    expect(screen.getByText("RAG 已命中相关风险信息，但最终回答没有采用。")).toBeInTheDocument();
    expect(screen.getByText("医学安全性专项分析")).toBeInTheDocument();
    expect(screen.getByText("安全门禁失败")).toBeInTheDocument();
    expect(screen.getByText(/2 条医学安全指南触发了安全门禁/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "← 返回归因任务" }));
    expect(await screen.findByTestId("return-state")).toHaveTextContent('"tab":"attribution"');
    expect(screen.getByTestId("return-state")).toHaveTextContent('"attributionTaskId":28');
  });
});
