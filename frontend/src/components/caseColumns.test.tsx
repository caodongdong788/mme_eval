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
  case_type: "medical_consultation",
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

    expect(screen.getByText("质量评级")).toBeInTheDocument();
    expect(screen.getByText("优秀")).toBeInTheDocument();
    expect(screen.getByText("运行验收")).toBeInTheDocument();
    expect(screen.getByText("通过")).toBeInTheDocument();
    expect(screen.getByText("稳定通过")).toBeInTheDocument();
    expect(screen.getByText("医学文献 RAG")).toBeInTheDocument();
    expect(screen.getByText("已触发并命中")).toBeInTheDocument();
    expect(screen.getByText("medical_consultation")).toBeInTheDocument();
    expect(screen.queryByText("症状识别")).not.toBeInTheDocument();
    expect(screen.queryByText("最终结论")).not.toBeInTheDocument();
  });

  it("shows concise actionable problem tags instead of one ambiguous failure string", () => {
    renderWithProviders(
      <MemoryRouter>
        <Table<CaseRow>
          rowKey="id"
          pagination={false}
          columns={buildCaseColumns(1, (tag) => ({
            plan_feasibility_gap: "方案可行性不足",
            executability_gap: "行动指引不清",
          })[tag] || tag)}
          dataSource={[{
            ...row,
            release_passed: false,
            failure_tags: ["plan_feasibility_gap", "executability_gap"],
          }]}
        />
      </MemoryRouter>,
    );

    expect(screen.getAllByText("主要问题").length).toBeGreaterThan(0);
    expect(screen.getByText("不通过")).toBeInTheDocument();
    expect(screen.getByText("方案可行性不足")).toBeInTheDocument();
    expect(screen.getByText("行动指引不清")).toBeInTheDocument();
    expect(screen.queryByText("失败标签")).not.toBeInTheDocument();
  });

  it("shows execution failure instead of a misleading quality score", () => {
    renderWithProviders(
      <MemoryRouter>
        <Table<CaseRow>
          rowKey="id"
          pagination={false}
          columns={buildCaseColumns(1, (tag) => tag)}
          dataSource={[{
            ...row,
            composite_score: 40,
            grade: "优秀",
            release_passed: false,
            failure_tags: ["adapter_error"],
          }]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("未产生回答")).toBeInTheDocument();
    expect(screen.getAllByText("执行失败")).toHaveLength(2);
    expect(screen.queryByText("40.0/40")).not.toBeInTheDocument();
  });
});
