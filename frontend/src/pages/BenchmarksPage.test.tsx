import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import BenchmarksPage from "./BenchmarksPage";
import { renderWithProviders } from "../test/renderWithProviders";

vi.mock("../api/index", () => ({
  api: {
    listBenchmarks: vi.fn().mockResolvedValue([
      {
        id: 13,
        name: "真实患者数据集benchmark",
        description: "",
        source: "uploaded",
        case_count: 63,
        levels: ["L2"],
        created_by: "曹冬东",
        default_evaluation_mode: "single_turn",
        suite_type: "capability",
      },
    ]),
    downloadBenchmarkUrl: (id: number) => `/api/benchmarks/${id}/download`,
  },
}));

describe("BenchmarksPage", () => {
  it("online upload only accepts Feishu URL (no file upload)", async () => {
    renderWithProviders(<BenchmarksPage />);

    fireEvent.click(await screen.findByRole("button", { name: /上传 benchmark/ }));
    fireEvent.click(screen.getByText("线上"));

    expect(screen.getByLabelText(/飞书 URL/)).toBeInTheDocument();
    expect(screen.getByText(/不支持文件上传/)).toBeInTheDocument();
    // 线上不再提供 JSONL / 文件上传入口
    expect(screen.queryByText(/JSONL/)).not.toBeInTheDocument();
    expect(screen.queryByText(/用例文件 \(\.yaml\)/)).not.toBeInTheDocument();
  });

  it("opens an append-only upload dialog from the benchmark row", async () => {
    renderWithProviders(<BenchmarksPage />);

    fireEvent.click(await screen.findByText("追加"));

    expect(screen.getByText("追加用例到 benchmark #13")).toBeInTheDocument();
    expect(screen.getByText("只新增用例，不修改当前评测集配置")).toBeInTheDocument();
    expect(screen.queryByLabelText("名称")).not.toBeInTheDocument();
    expect(screen.queryByText("默认对话模式")).not.toBeInTheDocument();
    expect(
      within(screen.getByRole("dialog")).getByRole("button", { name: /追\s*加/ })
    ).toBeInTheDocument();
  });
});
