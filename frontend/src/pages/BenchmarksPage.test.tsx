import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import BenchmarksPage from "./BenchmarksPage";
import { renderWithProviders } from "../test/renderWithProviders";
import { formatApiDateTime } from "../utils/datetime";

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
        created_at: "2026-08-13T02:10:00Z",
        updated_at: "2026-08-14T03:20:00Z",
        default_evaluation_mode: "single_turn",
        suite_type: "capability",
      },
    ]),
    downloadBenchmarkUrl: (id: number) => `/api/benchmarks/${id}/download`,
  },
}));

afterEach(cleanup);

describe("BenchmarksPage", () => {
  it("shows benchmark creation and update times", async () => {
    renderWithProviders(<BenchmarksPage />);

    expect(await screen.findByText(formatApiDateTime("2026-08-13T02:10:00Z"))).toBeInTheDocument();
    expect(screen.getByText(formatApiDateTime("2026-08-14T03:20:00Z"))).toBeInTheDocument();
  });

  it("provides one unified import form without an online/offline source choice", async () => {
    renderWithProviders(<BenchmarksPage />);

    fireEvent.click(await screen.findByRole("button", { name: /上传 benchmark/ }));

    expect(screen.queryByText("来源")).not.toBeInTheDocument();
    expect(screen.getByText(/用例文件 \(\.yaml \/ \.zip\)/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/用例链接/)).not.toBeInTheDocument();
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
