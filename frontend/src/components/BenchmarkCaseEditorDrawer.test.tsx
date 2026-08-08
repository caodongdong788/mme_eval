import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "../test/renderWithProviders";
import { BenchmarkCaseEditorDrawer } from "./BenchmarkCaseEditorDrawer";

const testCase = {
  schema_version: "2.0",
  sample_id: "case_55",
  scenario: "报告解读",
  case_type: "检查报告与指标解读",
  is_bug: "产品优化",
  level: "L2",
  initial_state: { user_profile: { 年龄: "36岁" }, Timeline: [] },
  turns: [{ role: "user", content: "帮我解读报告" }],
  evaluation: {
    dimension_criteria: { medical_safety: ["不得遗漏危险信号"] },
    guidelines: [],
  },
};

describe("BenchmarkCaseEditorDrawer criteria variant", () => {
  it("uses the benchmark structured editor without exposing YAML", () => {
    const onChange = vi.fn();
    renderWithProviders(
      <BenchmarkCaseEditorDrawer
        open
        loading={false}
        saving={false}
        source="uploaded"
        caseFile="cases.yaml"
        value={testCase}
        onChange={onChange}
        onClose={vi.fn()}
        variant="criteria"
        title="改判据 · 报告解读"
        benchmarkLabel="#12「真实患者数据集benchmark」"
        onOverwrite={vi.fn()}
      />
    );

    expect(screen.getByText("基本信息")).toBeInTheDocument();
    expect(screen.getByText("用户档案与过往事实")).toBeInTheDocument();
    expect(screen.getByText("八维评测要求")).toBeInTheDocument();
    expect(screen.getByText("指南扣分点（0）")).toBeInTheDocument();
    expect(screen.queryByText("查看源 YAML")).not.toBeInTheDocument();
    expect(screen.queryByText("源 YAML（只读）")).not.toBeInTheDocument();

    fireEvent.change(screen.getByDisplayValue("报告解读"), {
      target: { value: "报告复核" },
    });
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ scenario: "报告复核" }));
  });
});
