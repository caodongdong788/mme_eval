import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import BenchmarksPage from "./BenchmarksPage";
import { renderWithProviders } from "../test/renderWithProviders";

vi.mock("../api/index", () => ({
  api: {
    listBenchmarks: vi.fn().mockResolvedValue([]),
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
});
