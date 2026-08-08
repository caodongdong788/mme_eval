import type { CaseRow } from "../api";

export type CaseFilterField =
  | "sub_scenario"
  | "case_type"
  | "level"
  | "n_turns"
  | "composite_score"
  | "guideline_score"
  | "rag_status"
  | "release_passed"
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

export interface CaseFilterCondition {
  id: string;
  field: CaseFilterField;
  operator: CaseFilterOperator;
  value?: string;
}

export type CaseFilterFieldKind = "text" | "number" | "select";

export interface CaseFilterFieldDefinition {
  value: CaseFilterField;
  label: string;
  kind: CaseFilterFieldKind;
  options?: Array<{ value: string; label: string }>;
}

export type CaseFilterValueOptions = Partial<
  Record<CaseFilterField, Array<{ value: string; label: string }>>
>;

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
      { value: "triggered", label: "已触发（结果待解析）" },
      { value: "not_triggered", label: "未触发" },
      { value: "unknown", label: "链路未同步" },
    ],
  },
  {
    value: "release_passed",
    label: "最终结论",
    kind: "select",
    options: [
      { value: "true", label: "合格" },
      { value: "false", label: "不合格" },
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
  { value: "failure_tags", label: "失败标签", kind: "text" },
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
  { value: "equals", label: "等于" },
  { value: "not_equals", label: "不等于" },
  { value: "is_empty", label: "为空" },
  { value: "is_not_empty", label: "不为空" },
];

export function fieldDefinition(field: CaseFilterField): CaseFilterFieldDefinition {
  return CASE_FILTER_FIELDS.find((item) => item.value === field) ?? CASE_FILTER_FIELDS[0];
}

export function operatorsForField(field: CaseFilterField) {
  const kind = fieldDefinition(field).kind;
  if (kind === "number") return NUMBER_OPERATORS;
  if (kind === "select") return SELECT_OPERATORS;
  return TEXT_OPERATORS;
}

export function operatorNeedsValue(operator: CaseFilterOperator): boolean {
  return operator !== "is_empty" && operator !== "is_not_empty";
}

export function defaultOperator(field: CaseFilterField): CaseFilterOperator {
  const kind = fieldDefinition(field).kind;
  return kind === "text" ? "contains" : "equals";
}

export function isActiveCaseFilter(condition: CaseFilterCondition): boolean {
  return !operatorNeedsValue(condition.operator) || String(condition.value ?? "").trim() !== "";
}

function displayValue(
  row: CaseRow,
  field: CaseFilterField,
  queueIds: Set<string>,
  failureTagLabel: (tag: string) => string
): string | number | null {
  switch (field) {
    case "sub_scenario":
      return row.sub_scenario || row.sample_id;
    case "case_type":
      return row.case_type;
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
    case "release_passed":
      return String(row.release_passed);
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
  const actual = displayValue(row, condition.field, queueIds, failureTagLabel);
  if (condition.operator === "is_empty") return isEmpty(actual);
  if (condition.operator === "is_not_empty") return !isEmpty(actual);

  const expected = String(condition.value ?? "").trim();
  const kind = fieldDefinition(condition.field).kind;
  if (kind === "number") {
    const left = Number(actual);
    const right = Number(expected);
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
  const right = expected.toLocaleLowerCase();
  if (condition.operator === "contains") return left.includes(right);
  if (condition.operator === "not_contains") return !left.includes(right);
  if (condition.operator === "equals") return left === right;
  if (condition.operator === "not_equals") return left !== right;
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
