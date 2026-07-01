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
  it("reuses online upload entry for Feishu Base URL or JSONL", async () => {
    renderWithProviders(<BenchmarksPage />);

    fireEvent.click(await screen.findByRole("button", { name: /上传 benchmark/ }));
    fireEvent.click(screen.getByText("线上"));

    expect(screen.getByLabelText(/飞书 URL/)).toBeInTheDocument();
    expect(screen.getByText(/线上对话来源（JSONL \/ 飞书 URL）/)).toBeInTheDocument();
    expect(screen.getByText(/点击或拖拽 JSONL 文件，或直接使用上方飞书 URL/)).toBeInTheDocument();
  });
});
