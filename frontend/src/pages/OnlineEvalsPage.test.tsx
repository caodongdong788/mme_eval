import { fireEvent, screen } from "@testing-library/react";
import { Form } from "antd";
import { describe, expect, it, vi } from "vitest";
import type { OnlineEval } from "../api/index";
import { renderWithProviders } from "../test/renderWithProviders";
import OnlineEvalsPage from "./OnlineEvalsPage";
import { useOnlineEvalsPage } from "../hooks/useOnlineEvalsPage";

vi.mock("../hooks/useOnlineEvalsPage", () => ({
  useOnlineEvalsPage: vi.fn(),
}));

const row: OnlineEval = {
  id: 1,
  name: "线上问题",
  note: "骨健康批次",
  source_type: "benchmark",
  source_url: "",
  source_token: "",
  benchmark_id: 3,
  status: "success",
  progress: {},
  avg_score: 7.3,
  case_count: 151,
  gate_fail_count: 3,
  needs_review_count: 16,
  raw_import_payload: {},
  risk_tag_counter: {},
  judge_model: "Claude-Opus-4.7",
  judge_model_id: 2,
  judge_fingerprint: "",
  created_at: null,
  error_msg: "",
};

function useMockOnlineEvalsPage() {
  const [form] = Form.useForm();
  const [poolPathForm] = Form.useForm();
  return {
    form,
    poolPathForm,
    rows: [row],
    onlineBenchmarks: [],
    benchmarkNameById: { 3: "线上问题 benchmark" },
    judgeModels: [],
    loading: false,
    poolPaths: [{ id: 1, path: "骨健康/满意样本", description: "", case_count: 2 }],
    poolLoading: false,
    poolError: null,
    poolSubmitting: false,
    poolImporting: false,
    poolAddingCaseId: null,
    poolExportingPathId: null,
    poolUpdatingPathId: null,
    poolDeletingPathId: null,
    poolEditingPath: null,
    poolDetailPath: null,
    poolDetailCases: [],
    poolDetailLoading: false,
    poolDeletingCaseId: null,
    progress: {},
    loadError: null,
    reload: vi.fn(),
    submitting: false,
    submit: vi.fn(),
    detail: null,
    detailLoading: false,
    deletingCaseId: null,
    rescoringCaseId: null,
    openDetail: vi.fn(),
    deleteEval: vi.fn(),
    deleteCase: vi.fn(),
    rescoreCase: vi.fn(),
    reloadPoolPaths: vi.fn(),
    createPoolPath: vi.fn(),
    importPoolPathFromFeishu: vi.fn(),
    addCaseToPool: vi.fn(),
    updatePoolPath: vi.fn(),
    openPoolPathEdit: vi.fn(),
    closePoolPathEdit: vi.fn(),
    openPoolPathDetail: vi.fn(),
    closePoolPathDetail: vi.fn(),
    deletePoolPath: vi.fn(),
    deletePoolCase: vi.fn(),
    exportPoolPath: vi.fn(),
    closeDetail: vi.fn(),
  };
}

describe("OnlineEvalsPage", () => {
  it("renders eval name and row actions", () => {
    vi.mocked(useOnlineEvalsPage).mockImplementation(useMockOnlineEvalsPage);

    renderWithProviders(<OnlineEvalsPage />);

    expect(screen.getAllByText("评测名称").length).toBeGreaterThan(0);
    expect(screen.getByText("线上问题")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "详情" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /删除/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "标注池" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "标注池" }));
    expect(screen.getByText("骨健康/满意样本")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /新增标注集/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /飞书导入/ })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /删除/ }).length).toBeGreaterThan(0);
  });
});
