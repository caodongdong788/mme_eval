import { describe, expect, it, vi } from "vitest";
import { CasePreviewRejudgePanel } from "./CasePreviewRejudgePanel";
import type { PreviewRejudgeResult } from "../api/index";
import { renderWithProviders } from "../test/renderWithProviders";

const scoreBase = {
  hard_gate_passed: true,
  gate_passed: true,
  release_passed: true,
  composite_score: 0.92,
  grade: "优秀",
  dimension_scores: {},
  dimension_max: {},
  score_profile: "default",
  score_deductions: [] as string[],
  failure_tags: [],
  needs_human_review: false,
  verdicts: [],
};

const previewResult: PreviewRejudgeResult = {
  sample_id: "bc_001",
  changed: true,
  case_result: {},
  current: scoreBase,
  preview: {
    ...scoreBase,
    release_passed: false,
    composite_score: 0.71,
    grade: "良好",
    score_deductions: ["功能：未命中 must_have"],
  },
};

describe("CasePreviewRejudgePanel", () => {
  it("matches snapshot without preview result", () => {
    const { container } = renderWithProviders(
      <CasePreviewRejudgePanel
        previewing={false}
        yamlLoading={false}
        yamlText="sample_id: bc_001"
        previewResult={null}
        onPreview={vi.fn()}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it("matches snapshot with preview result", () => {
    const { container } = renderWithProviders(
      <CasePreviewRejudgePanel
        previewing={false}
        yamlLoading={false}
        yamlText="sample_id: bc_001"
        previewResult={previewResult}
        onPreview={vi.fn()}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
