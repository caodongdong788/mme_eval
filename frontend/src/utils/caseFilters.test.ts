import { describe, expect, it } from "vitest";
import type { CaseBrief, CaseRow } from "../api";
import {
  BENCHMARK_CASE_FILTER_FIELDS,
  buildBenchmarkCaseFilterValueOptions,
  buildCaseFilterValueOptions,
  type CaseFilterCondition,
  filterBenchmarkCaseRows,
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

const benchmarkRows: CaseBrief[] = [
  {
    sample_id: "case_1",
    scenario: "潮热用药",
    level: "L2",
    case_type: "治疗副作用与不适归因",
    is_bug: "产品优化",
  },
  {
    sample_id: "case_7",
    scenario: "血压用药",
    level: "L3",
    case_type: "症状判断与就医分诊",
    is_bug: "bug修复",
  },
];

describe("filterBenchmarkCaseRows", () => {
  it("supports every benchmark table column with AND semantics", () => {
    const result = filterBenchmarkCaseRows(
      benchmarkRows,
      [
        condition("sample_id", "contains", "case_7"),
        condition("scenario", "equals", "血压用药"),
        condition("level", "equals", "L3"),
        condition("case_type", "contains", "就医分诊"),
        condition("is_bug", "equals", "bug修复"),
        condition("benchmark_action", "equals", "deletable"),
      ],
      false
    );
    expect(result).toEqual([benchmarkRows[1]]);
  });

  it("distinguishes deletable and read-only operation columns", () => {
    const readOnly = [condition("benchmark_action", "equals", "read_only")];
    expect(filterBenchmarkCaseRows(benchmarkRows, readOnly, true)).toEqual(benchmarkRows);
    expect(filterBenchmarkCaseRows(benchmarkRows, readOnly, false)).toEqual([]);
  });

  it("provides autocomplete values for benchmark text columns", () => {
    const options = buildBenchmarkCaseFilterValueOptions(benchmarkRows);
    expect(options.sample_id?.map((item) => item.value)).toEqual(["case_1", "case_7"]);
    expect(options.scenario?.map((item) => item.value)).toEqual(["潮热用药", "血压用药"]);
    expect(options.case_type?.map((item) => item.value)).toEqual([
      "治疗副作用与不适归因",
      "症状判断与就医分诊",
    ]);
    expect(options.is_bug?.map((item) => item.value)).toEqual(["产品优化", "bug修复"]);
    expect(BENCHMARK_CASE_FILTER_FIELDS.map((item) => item.label)).toEqual([
      "Case ID",
      "场景",
      "Level",
      "Case 类型",
      "问题属性",
      "操作",
    ]);
  });
});
