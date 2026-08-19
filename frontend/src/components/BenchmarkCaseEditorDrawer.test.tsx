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
    dimension_criteria: {
      medical_safety: {
        criteria: ["不得遗漏危险信号"],
        reference_answers: ["先说明危险信号，再建议尽快就医。"],
      },
    },
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

    fireEvent.click(screen.getByText("八维评测要求"));
    fireEvent.click(screen.getByText("医学安全性"));
    expect(screen.getByText("好答案（可选）")).toBeInTheDocument();
    expect(screen.getByDisplayValue("先说明危险信号，再建议尽快就医。")).toBeInTheDocument();
  });

  it("groups guidelines by dimension in doctor, nurse, patient order", () => {
    const groupedCase = {
      ...testCase,
      evaluation: {
        ...testCase.evaluation,
        guidelines: [
          { id: "g01", dimension: "empathy", criteria: ["患者检查点一"] },
          { id: "g02", dimension: "medical_safety", criteria: ["医生检查点"] },
          { id: "g03", dimension: "personalization", criteria: ["护士检查点"] },
          { id: "g04", dimension: "empathy", criteria: ["患者检查点二"] },
        ],
      },
    };
    renderWithProviders(
      <BenchmarkCaseEditorDrawer open loading={false} saving={false} source="uploaded" caseFile="cases.yaml" value={groupedCase} onChange={vi.fn()} onClose={vi.fn()} />
    );

    fireEvent.click(screen.getByText("指南扣分点（4）"));

    const roleGroups = Array.from(document.body.querySelectorAll(".case-editor-guideline-role-group"));
    expect(roleGroups).toHaveLength(3);
    expect(roleGroups[0]).toHaveTextContent("医生端");
    expect(roleGroups[0]).toHaveTextContent("医学安全性");
    expect(roleGroups[1]).toHaveTextContent("护士端");
    expect(roleGroups[1]).toHaveTextContent("个性化相关性");
    expect(roleGroups[2]).toHaveTextContent("患者端");
    expect(roleGroups[2]).toHaveTextContent("患者检查点一");
    expect(roleGroups[2]).toHaveTextContent("患者检查点二");
    expect(roleGroups[2].querySelectorAll(".case-editor-guideline-dimension-group")).toHaveLength(1);
  });

  it("shows a non-blocking warning for cross-dimension ownership risks", () => {
    renderWithProviders(
      <BenchmarkCaseEditorDrawer
        open
        loading={false}
        saving={false}
        source="uploaded"
        caseFile="cases.yaml"
        value={{
          ...testCase,
          evaluation: {
            ...testCase.evaluation,
            guidelines: [{
              id: "g01",
              dimension: "empathy",
              criteria: ["应明确提示出现呼吸困难时立即急诊就医"],
            }],
          },
        }}
        onChange={vi.fn()}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText("发现 1 处跨维度归属或重复扣分风险")).toBeInTheDocument();
    expect(screen.getByText(/主责更接近医学安全性/)).toBeInTheDocument();
  });
});
