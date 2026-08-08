import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "../test/renderWithProviders";
import { ReferenceAnswersPanel, referenceAnswerEntries } from "./ReferenceAnswersPanel";

const evaluation = {
  dimension_criteria: {
    clinical_inquiry: {
      criteria: ["追问病程"],
      reference_answers: ["先确认症状持续多久、是否加重。"],
    },
  },
  guidelines: [{
    id: "g01",
    dimension: "medical_safety",
    criteria: ["不得延误就医"],
    reference_answers: ["建议今天联系主管医生。"],
  }],
};

describe("ReferenceAnswersPanel", () => {
  it("shows dimension and guideline reference answers from the frozen case", () => {
    renderWithProviders(<ReferenceAnswersPanel evaluation={evaluation} />);

    expect(screen.getByText("好答案参考")).toBeInTheDocument();
    expect(screen.getByText("八维 · 临床追问充分性")).toBeInTheDocument();
    expect(screen.getByText("指南 g01 · 医学安全性")).toBeInTheDocument();
    expect(screen.getByText("建议今天联系主管医生。")).toBeInTheDocument();
  });

  it("does not create entries for empty values", () => {
    expect(referenceAnswerEntries({ dimension_criteria: { empathy: { reference_answers: null } } })).toEqual([]);
  });
});
