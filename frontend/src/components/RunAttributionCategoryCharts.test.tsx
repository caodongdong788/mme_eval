import { screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "../test/renderWithProviders";
import {
  filterSecondLevelCategories,
  RunAttributionCategoryCharts,
} from "./RunAttributionCategoryCharts";

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
    expect(screen.getByText(/每个 Case 仅采用最新一次成功归因/)).toBeInTheDocument();
    expect(screen.getByText(/已归因/)).toHaveTextContent("已归因 3 个 Case");
    expect(screen.getByText(/点击柱形筛选右侧二级分类/)).toBeInTheDocument();
  });

  it("filters second-level categories by their selected parent", () => {
    const rows = [
      { key: "rag:missing", label: "缺少 RAG 引用", case_count: 2, parent_key: "rag" },
      { key: "prompt:boundary", label: "未说明适用边界", case_count: 1, parent_key: "prompt" },
    ];

    expect(filterSecondLevelCategories(rows, "rag")).toEqual([rows[0]]);
    expect(filterSecondLevelCategories(rows, null)).toEqual(rows);
  });

  it("keeps the current charts visible during a background refresh", () => {
    const { container } = renderWithProviders(
      <RunAttributionCategoryCharts
        loading
        stats={{
          attributed_case_count: 3,
          first_level: [{ key: "rag", label: "RAG 优化", case_count: 2 }],
          second_level: [],
        }}
      />
    );

    expect(container).toHaveTextContent("归因一级分类");
    expect(container).toHaveTextContent("归因二级分类");
    expect(container.querySelector(".ant-spin")).not.toBeInTheDocument();
  });
});
