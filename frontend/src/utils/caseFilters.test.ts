import { describe, expect, it } from "vitest";
import type { CaseRow } from "../api";
import {
  buildCaseFilterValueOptions,
  type CaseFilterCondition,
  filterCaseRows,
} from "./caseFilters";

const rows: CaseRow[] = [
  {
    id: 1,
    sample_id: "a",
    scenario: "症状识别",
    case_type: "consultation",
    sub_scenario: "乳房肿块",
    level: "L2",
    medical_safety_passed: true,
    release_passed: true,
    composite_score: 41.5,
    grade: "优秀",
    stability: "stable_pass",
    guideline_earned: 6,
    guideline_max: 6,
    n_turns: 1,
    rag_status: "hit",
    failure_tags: [],
  },
  {
    id: 2,
    sample_id: "b",
    scenario: "用药管理",
    case_type: "medication",
    sub_scenario: "内分泌治疗漏服",
    level: "L2",
    medical_safety_passed: true,
    release_passed: false,
    composite_score: 25,
    grade: "不合格",
    stability: "flaky",
    guideline_earned: 5,
    guideline_max: 6,
    n_turns: 2,
    rag_status: "not_triggered",
    failure_tags: ["missing_followup"],
    review: { verdict: "override", count: 1 },
  },
];

function condition(
  field: CaseFilterCondition["field"],
  operator: CaseFilterCondition["operator"],
  value?: string
): CaseFilterCondition {
  return { id: `${field}-${operator}`, field, operator, value };
}

describe("filterCaseRows", () => {
  it("combines arbitrary table-column conditions with AND semantics", () => {
    const result = filterCaseRows(
      rows,
      [
        condition("case_type", "contains", "medication"),
        condition("composite_score", "lt", "30"),
        condition("stability", "equals", "flaky"),
      ],
      new Set()
    );
    expect(result.map((row) => row.sample_id)).toEqual(["b"]);
  });

  it("filters displayed guideline scores and empty failure labels", () => {
    expect(
      filterCaseRows(rows, [condition("guideline_score", "equals", "5/6")], new Set())
    ).toHaveLength(1);
    expect(
      filterCaseRows(rows, [condition("failure_tags", "is_empty")], new Set())
    ).toEqual([rows[0]]);
  });

  it("supports review content and pending queue", () => {
    expect(
      filterCaseRows(rows, [condition("review", "equals", "override")], new Set())
    ).toEqual([rows[1]]);
    expect(
      filterCaseRows(rows, [condition("review", "equals", "pending")], new Set(["a"]))
    ).toEqual([rows[0]]);
  });

  it("filters by real RAG invocation state", () => {
    expect(
      filterCaseRows(rows, [condition("rag_status", "equals", "hit")], new Set())
    ).toEqual([rows[0]]);
    expect(
      filterCaseRows(rows, [condition("rag_status", "equals", "not_triggered")], new Set())
    ).toEqual([rows[1]]);
  });
});

describe("buildCaseFilterValueOptions", () => {
  it("offers existing table content for selection", () => {
    const options = buildCaseFilterValueOptions(rows, (tag) =>
      tag === "missing_followup" ? "追问不足" : tag
    );
    expect(options.sub_scenario?.map((item) => item.value)).toEqual([
      "乳房肿块",
      "内分泌治疗漏服",
    ]);
    expect(options.case_type?.map((item) => item.value)).toEqual([
      "consultation",
      "medication",
    ]);
    expect(options.guideline_score?.map((item) => item.value)).toEqual(["6/6", "5/6"]);
    expect(options.failure_tags?.map((item) => item.value)).toEqual(["追问不足"]);
    expect(options.rag_status?.map((item) => item.value)).toEqual(["hit", "not_triggered"]);
  });
});
