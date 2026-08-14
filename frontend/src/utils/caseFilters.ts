import type { CaseBrief, CaseRow } from "../api";

export type CaseFilterField =
  | "sample_id"
  | "scenario"
  | "sub_scenario"
  | "case_type"
  | "is_bug"
  | "benchmark_action"
  | "level"
  | "n_turns"
  | "composite_score"
  | "guideline_score"
  | "rag_status"
  | "grade"
  | "stability"
  | "failure_tags"
  | "review";

export type CaseFilterOperator =
  | "contains"
  | "not_contains"
  | "equals"
  | "not_equals"
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "is_empty"
  | "is_not_empty";

export interface FilterCondition<Field extends string = string> {
  id: string;
  field: Field;
  operator: CaseFilterOperator;
  /**
   * `contains` / `not_contains` on an enum accept several values.  Values in
   * the same condition use OR semantics: e.g. 综合评价「包含 优秀、良好」.
   */
  value?: string | string[];
}

export type CaseFilterCondition = FilterCondition<CaseFilterField>;

export type CaseFilterFieldKind = "text" | "number" | "select" | "multi_select";

export interface FilterFieldDefinition<Field extends string = string> {
  value: Field;
  label: string;
  kind: CaseFilterFieldKind;
  options?: Array<{ value: string; label: string }>;
}

export type CaseFilterFieldDefinition = FilterFieldDefinition<CaseFilterField>;

export type FilterValueOptions<Field extends string = string> = Partial<
  Record<Field, Array<{ value: string; label: string }>>
>;

export type CaseFilterValueOptions = FilterValueOptions<CaseFilterField>;

export const CASE_FILTER_FIELDS: CaseFilterFieldDefinition[] = [
  { value: "sub_scenario", label: "场景描述", kind: "text" },
  { value: "case_type", label: "类别", kind: "text" },
  {
    value: "level",
    label: "Level",
    kind: "select",
    options: ["L1", "L2", "L3", "L4"].map((value) => ({ value, label: value })),
  },
  { value: "n_turns", label: "轮数", kind: "number" },
  { value: "composite_score", label: "总分", kind: "number" },
  { value: "guideline_score", label: "指南得分", kind: "text" },
  {
    value: "rag_status",
    label: "医学文献 RAG",
    kind: "select",
    options: [
      { value: "hit", label: "已触发并命中" },
      { value: "miss", label: "已触发未命中" },
      { value: "failed", label: "调用失败" },
      { value: "triggered", label: "已触发" },
      { value: "not_triggered", label: "未触发" },
      { value: "unknown", label: "链路未同步" },
    ],
  },
  {
    value: "grade",
    label: "综合评价",
    kind: "select",
    options: [
      { value: "优秀", label: "优秀" },
      { value: "良好", label: "良好" },
      { value: "合格", label: "合格" },
      { value: "不合格", label: "不合格" },
      { value: "判分异常", label: "判分异常" },
    ],
  },
  {
    value: "stability",
    label: "稳定性",
    kind: "select",
    options: [
      { value: "stable_pass", label: "稳过" },
      { value: "flaky", label: "抖动" },
      { value: "stable_fail", label: "稳挂" },
    ],
  },
  { value: "failure_tags", label: "失败标签", kind: "multi_select" },
  {
    value: "review",
    label: "人审结果",
    kind: "select",
    options: [
      { value: "agree", label: "同意" },
      { value: "override", label: "推翻" },
      { value: "none", label: "未审" },
      { value: "pending", label: "待审队列" },
    ],
  },
];

const LEVEL_OPTIONS = ["L1", "L2", "L3", "L4"].map((value) => ({ value, label: value }));

export const BENCHMARK_CASE_FILTER_FIELDS: CaseFilterFieldDefinition[] = [
  { value: "sample_id", label: "Case ID", kind: "text" },
  { value: "scenario", label: "场景", kind: "text" },
  { value: "level", label: "Level", kind: "select", options: LEVEL_OPTIONS },
  { value: "case_type", label: "Case 类型", kind: "text" },
  { value: "is_bug", label: "问题属性", kind: "text" },
  {
    value: "benchmark_action",
    label: "操作",
    kind: "select",
    options: [
      { value: "deletable", label: "可删除" },
      { value: "read_only", label: "只读" },
    ],
  },
];

const TEXT_OPERATORS: Array<{ value: CaseFilterOperator; label: string }> = [
  { value: "contains", label: "包含" },
  { value: "not_contains", label: "不包含" },
  { value: "equals", label: "等于" },
  { value: "not_equals", label: "不等于" },
  { value: "is_empty", label: "为空" },
  { value: "is_not_empty", label: "不为空" },
];

const NUMBER_OPERATORS: Array<{ value: CaseFilterOperator; label: string }> = [
  { value: "equals", label: "等于" },
  { value: "not_equals", label: "不等于" },
  { value: "gt", label: "大于" },
  { value: "gte", label: "大于等于" },
  { value: "lt", label: "小于" },
  { value: "lte", label: "小于等于" },
  { value: "is_empty", label: "为空" },
  { value: "is_not_empty", label: "不为空" },
];

const SELECT_OPERATORS: Array<{ value: CaseFilterOperator; label: string }> = [
  { value: "contains", label: "包含" },
  { value: "not_contains", label: "不包含" },
  { value: "equals", label: "等于" },
  { value: "not_equals", label: "不等于" },
  { value: "is_empty", label: "为空" },
  { value: "is_not_empty", label: "不为空" },
];

const MULTI_SELECT_OPERATORS: Array<{ value: CaseFilterOperator; label: string }> = [
  { value: "contains", label: "包含" },
  { value: "not_contains", label: "不包含" },
  { value: "is_empty", label: "为空" },
  { value: "is_not_empty", label: "不为空" },
];

export function fieldDefinition<Field extends string>(
  field: Field,
  fields: FilterFieldDefinition<Field>[]
): FilterFieldDefinition<Field> {
  return fields.find((item) => item.value === field) ?? fields[0] ?? ({
    value: field,
    label: field,
    kind: "text",
  } as FilterFieldDefinition<Field>);
}

export function operatorsForField<Field extends string>(
  field: Field,
  fields: FilterFieldDefinition<Field>[]
) {
  const kind = fieldDefinition(field, fields).kind;
  if (kind === "number") return NUMBER_OPERATORS;
  if (kind === "multi_select") return MULTI_SELECT_OPERATORS;
  if (kind === "select") return SELECT_OPERATORS;
  return TEXT_OPERATORS;
}

export function operatorNeedsValue(operator: CaseFilterOperator): boolean {
  return operator !== "is_empty" && operator !== "is_not_empty";
}

export function defaultOperator<Field extends string>(
  field: Field,
  fields: FilterFieldDefinition<Field>[]
): CaseFilterOperator {
  const kind = fieldDefinition(field, fields).kind;
  return kind === "text" || kind === "multi_select" ? "contains" : "equals";
}

export function isActiveCaseFilter(condition: CaseFilterCondition): boolean {
  return isActiveFilter(condition);
}

export function isActiveFilter<Field extends string>(condition: FilterCondition<Field>): boolean {
  if (!operatorNeedsValue(condition.operator)) return true;
  if (Array.isArray(condition.value)) return condition.value.some((value) => value.trim() !== "");
  return String(condition.value ?? "").trim() !== "";
}

function expectedValues(value: FilterCondition["value"]): string[] {
  const values = Array.isArray(value) ? value : [value];
  return values.map((item) => String(item ?? "").trim()).filter(Boolean);
}

function displayValue(
  row: CaseRow,
  field: CaseFilterField,
  queueIds: Set<string>,
  failureTagLabel: (tag: string) => string
): string | number | null {
  switch (field) {
    case "sample_id":
      return row.sample_id;
    case "scenario":
      return row.scenario;
    case "sub_scenario":
      return row.sub_scenario || row.sample_id;
    case "case_type":
      return row.case_type;
    case "is_bug":
    case "benchmark_action":
      return null;
    case "level":
      return row.level;
    case "n_turns":
      return row.n_turns ?? 1;
    case "composite_score":
      return row.composite_score ?? null;
    case "guideline_score":
      return row.guideline_max
        ? `${row.guideline_earned ?? 0}/${row.guideline_max}`
        : "";
    case "rag_status":
      return row.rag_status || "unknown";
    case "grade":
      return row.judge_error
        ? "判分异常"
        : row.grade || (row.release_passed ? "合格" : "不合格");
    case "stability":
      return row.stability;
    case "failure_tags":
      return (row.failure_tags || [])
        .flatMap((tag) => [tag, failureTagLabel(tag)])
        .join("、");
    case "review":
      if (queueIds.has(row.sample_id)) return "pending";
      return row.review?.verdict ?? "none";
  }
}

function isEmpty(value: string | number | null): boolean {
  return value == null || String(value).trim() === "";
}

function matchesCondition(
  row: CaseRow,
  condition: CaseFilterCondition,
  queueIds: Set<string>,
  failureTagLabel: (tag: string) => string
): boolean {
  if (condition.field === "failure_tags") {
    const values = (row.failure_tags || []).flatMap((tag) => [
      tag.toLocaleLowerCase(),
      failureTagLabel(tag).toLocaleLowerCase(),
    ]);
    if (condition.operator === "is_empty") return values.length === 0;
    if (condition.operator === "is_not_empty") return values.length > 0;
    const expected = expectedValues(condition.value).map((value) => value.toLocaleLowerCase());
    const contains = expected.some((item) => values.some((value) => value === item));
    if (condition.operator === "contains" || condition.operator === "equals") return contains;
    if (condition.operator === "not_contains" || condition.operator === "not_equals") return !contains;
    return false;
  }
  const actual = displayValue(row, condition.field, queueIds, failureTagLabel);
  return matchesValue(actual, condition, CASE_FILTER_FIELDS);
}

function matchesValue(
  actual: string | number | null,
  condition: CaseFilterCondition,
  fields: CaseFilterFieldDefinition[]
): boolean {
  if (condition.operator === "is_empty") return isEmpty(actual);
  if (condition.operator === "is_not_empty") return !isEmpty(actual);

  const expected = expectedValues(condition.value);
  const kind = fieldDefinition(condition.field, fields).kind;
  if (kind === "number") {
    const left = Number(actual);
    const right = Number(expected[0]);
    if (!Number.isFinite(left) || !Number.isFinite(right)) return false;
    if (condition.operator === "equals") return left === right;
    if (condition.operator === "not_equals") return left !== right;
    if (condition.operator === "gt") return left > right;
    if (condition.operator === "gte") return left >= right;
    if (condition.operator === "lt") return left < right;
    if (condition.operator === "lte") return left <= right;
    return false;
  }

  const left = String(actual ?? "").toLocaleLowerCase();
  const expectedLower = expected.map((value) => value.toLocaleLowerCase());
  if (condition.operator === "contains") return expectedLower.some((value) => left.includes(value));
  if (condition.operator === "not_contains") return expectedLower.every((value) => !left.includes(value));
  if (condition.operator === "equals") return expectedLower.some((value) => left === value);
  if (condition.operator === "not_equals") return expectedLower.every((value) => left !== value);
  return false;
}

export function filterCaseRows(
  rows: CaseRow[],
  conditions: CaseFilterCondition[],
  queueIds: Set<string>,
  failureTagLabel: (tag: string) => string = (tag) => tag
): CaseRow[] {
  const active = conditions.filter(isActiveCaseFilter);
  if (active.length === 0) return rows;
  return rows.filter((row) =>
    active.every((condition) => matchesCondition(row, condition, queueIds, failureTagLabel))
  );
}

export function buildCaseFilterValueOptions(
  rows: CaseRow[],
  failureTagLabel: (tag: string) => string
): CaseFilterValueOptions {
  const unique = (values: Array<string | number | null | undefined>) =>
    Array.from(
      new Set(values.map((value) => String(value ?? "").trim()).filter(Boolean))
    ).map((value) => ({ value, label: value }));

  return {
    sub_scenario: unique(rows.map((row) => row.sub_scenario || row.sample_id)),
    case_type: unique(rows.map((row) => row.case_type)),
    guideline_score: unique(
      rows.map((row) =>
        row.guideline_max ? `${row.guideline_earned ?? 0}/${row.guideline_max}` : ""
      )
    ),
    rag_status: unique(rows.map((row) => row.rag_status || "unknown")),
    failure_tags: unique(
      rows.flatMap((row) => (row.failure_tags || []).map((tag) => failureTagLabel(tag)))
    ),
  };
}

function displayBenchmarkValue(
  row: CaseBrief,
  field: CaseFilterField,
  isBuiltin: boolean
): string | null {
  switch (field) {
    case "sample_id":
      return row.sample_id;
    case "scenario":
      return row.scenario;
    case "level":
      return row.level;
    case "case_type":
      return row.case_type;
    case "is_bug":
      return row.is_bug;
    case "benchmark_action":
      return isBuiltin ? "read_only" : "deletable";
    default:
      return null;
  }
}

export function filterBenchmarkCaseRows(
  rows: CaseBrief[],
  conditions: CaseFilterCondition[],
  isBuiltin: boolean
): CaseBrief[] {
  const active = conditions.filter(isActiveCaseFilter);
  if (active.length === 0) return rows;
  return rows.filter((row) =>
    active.every((condition) =>
      matchesValue(
        displayBenchmarkValue(row, condition.field, isBuiltin),
        condition,
        BENCHMARK_CASE_FILTER_FIELDS
      )
    )
  );
}

export function buildBenchmarkCaseFilterValueOptions(
  rows: CaseBrief[]
): CaseFilterValueOptions {
  const unique = (values: Array<string | null | undefined>) =>
    Array.from(new Set(values.map((value) => String(value ?? "").trim()).filter(Boolean))).map(
      (value) => ({ value, label: value })
    );

  return {
    sample_id: unique(rows.map((row) => row.sample_id)),
    scenario: unique(rows.map((row) => row.scenario)),
    case_type: unique(rows.map((row) => row.case_type)),
    is_bug: unique(rows.map((row) => row.is_bug)),
  };
}
