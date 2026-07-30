import { screen } from "@testing-library/react";
import { Table } from "antd";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { CaseRow } from "../api";
import { renderWithProviders } from "../test/renderWithProviders";
import { buildCaseColumns } from "./caseColumns";

const row: CaseRow = {
  id: 1,
  sample_id: "case-1",
  scenario: "症状识别",
  sub_scenario: "测试场景",
  level: "L2",
  medical_safety_passed: true,
  release_passed: true,
  composite_score: 42,
  grade: "优秀",
  stability: "stable_pass",
  guideline_earned: 6,
  guideline_max: 6,
  rag_status: "hit",
  failure_tags: [],
};

describe("buildCaseColumns", () => {
  it("shows the complete grade instead of reducing it to pass or fail", () => {
    renderWithProviders(
      <MemoryRouter>
        <Table<CaseRow>
          rowKey="id"
          pagination={false}
          columns={buildCaseColumns(1, (tag) => tag)}
          dataSource={[row]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("综合评级")).toBeInTheDocument();
    expect(screen.getByText("优秀")).toBeInTheDocument();
    expect(screen.getByText("医学文献 RAG")).toBeInTheDocument();
    expect(screen.getByText("已触发并命中")).toBeInTheDocument();
    expect(screen.queryByText("最终结论")).not.toBeInTheDocument();
  });
});
