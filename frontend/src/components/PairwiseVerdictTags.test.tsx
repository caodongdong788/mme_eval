import { describe, expect, it } from "vitest";
import type { PairwiseCaseVerdict } from "../api/index";
import {
  PairwiseConfidenceTag,
  PairwiseHeaderHint,
  PairwiseVerdictTag,
} from "./PairwiseVerdictTags";
import { renderWithProviders } from "../test/renderWithProviders";

const baseVerdict = (over: Partial<PairwiseCaseVerdict> = {}): PairwiseCaseVerdict => ({
  sample_id: "bc_001",
  winner: "B",
  confidence: "high",
  confidence_kind: "high",
  reason: "test",
  human_calibrated: false,
  swap_consistent: true,
  dimension_winners: {},
  ...over,
});

describe("PairwiseVerdictTag", () => {
  it("matches snapshot for B winner with human calibration", () => {
    const { container } = renderWithProviders(
      <PairwiseVerdictTag verdict={baseVerdict({ human_calibrated: true })} />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it("matches snapshot for tie", () => {
    const { container } = renderWithProviders(
      <PairwiseVerdictTag verdict={baseVerdict({ winner: "tie" })} />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});

describe("PairwiseConfidenceTag", () => {
  it("matches snapshot for order-sensitive low confidence", () => {
    const { container } = renderWithProviders(
      <PairwiseConfidenceTag verdict={baseVerdict({ confidence_kind: "order", winner: "tie" })} />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});

describe("PairwiseHeaderHint", () => {
  it("matches snapshot", () => {
    const { container } = renderWithProviders(
      <PairwiseHeaderHint label="置信" hint="tooltip text" />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
