import { screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "../test/renderWithProviders";
import { RunAttributionCategoryCharts } from "./RunAttributionCategoryCharts";

describe("RunAttributionCategoryCharts", () => {
  beforeAll(() => {
    vi.stubGlobal("ResizeObserver", class {
      observe() {}
      unobserve() {}
      disconnect() {}
    });
  });

  it("shows the two classification levels and explains the deduplication scope", () => {
    renderWithProviders(
      <RunAttributionCategoryCharts
        loading={false}
        stats={{
          attributed_case_count: 3,
          first_level: [
            { key: "rag", label: "RAG 优化", case_count: 2 },
          ],
          second_level: [
            {
              key: "rag:缺少 RAG 引用",
              label: "缺少 RAG 引用",
              case_count: 2,
              parent_key: "rag",
              parent_label: "RAG 优化",
            },
          ],
        }}
      />
    );

    expect(screen.getByText("归因一级分类")).toBeInTheDocument();
    expect(screen.getByText("归因二级分类")).toBeInTheDocument();
    expect(screen.getByText(/每个 Case 仅采用最新一次成功归因/)).toHaveTextContent(
      "已归因 3 个 Case"
    );
  });
});
