import type { RunSummary } from "../api";
import {
  fieldDefinition,
  operatorNeedsValue,
  type FilterCondition,
  type FilterFieldDefinition,
  type FilterValueOptions,
} from "./caseFilters";

export type RunFilterField =
  | "id"
  | "name"
  | "trigger_type"
  | "status"
  | "pass_rate"
  | "medical_safety_failed"
  | "n_runs"
  | "created_by"
  | "created_at";

export type RunFilterCondition = FilterCondition<RunFilterField>;

export const RUN_FILTER_FIELDS: FilterFieldDefinition<RunFilterField>[] = [
  { value: "id", label: "ID", kind: "number" },
  { value: "name", label: "名称", kind: "text" },
  {
    value: "trigger_type", label: "任务类型", kind: "select", options: [
      { value: "manual", label: "人工触发" }, { value: "scheduled", label: "定时任务触发" }, { value: "open_api", label: "Open API 触发" },
    ],
  },
  {
    value: "status", label: "状态", kind: "select", options: [
      { value: "pending", label: "等待中" }, { value: "running", label: "运行中" }, { value: "success", label: "成功" }, { value: "failed", label: "失败" },
    ],
  },
  { value: "pass_rate", label: "通过率（%）", kind: "number" },
  { value: "medical_safety_failed", label: "安全失败", kind: "number" },
  { value: "n_runs", label: "N", kind: "number" },
  { value: "created_by", label: "创建人", kind: "text" },
  { value: "created_at", label: "创建时间", kind: "text" },
];

function actual(row: RunSummary, field: RunFilterField): string | number | null {
  switch (field) {
    case "id": return row.id;
    case "name": return row.name || row.run_slug;
    case "trigger_type": return row.trigger_type || "manual";
    case "status": return row.status;
    case "pass_rate": return Number((row.pass_rate * 100).toFixed(4));
    case "medical_safety_failed": return row.medical_safety_failed;
    case "n_runs": return row.n_runs;
    case "created_by": return row.created_by || "";
    case "created_at": return row.created_at || "";
  }
}

function matches(row: RunSummary, condition: RunFilterCondition): boolean {
  const value = actual(row, condition.field);
  const empty = value == null || String(value).trim() === "";
  if (condition.operator === "is_empty") return empty;
  if (condition.operator === "is_not_empty") return !empty;
  const expected = (Array.isArray(condition.value) ? condition.value : [condition.value])
    .map((item) => String(item ?? "").trim())
    .filter(Boolean);
  const kind = fieldDefinition(condition.field, RUN_FILTER_FIELDS).kind;
  if (kind === "number") {
    const left = Number(value), right = Number(expected[0]);
    if (!Number.isFinite(left) || !Number.isFinite(right)) return false;
    return ({ equals: left === right, not_equals: left !== right, gt: left > right, gte: left >= right, lt: left < right, lte: left <= right } as Record<string, boolean>)[condition.operator] ?? false;
  }
  const left = String(value ?? "").toLocaleLowerCase();
  const lower = expected.map((item) => item.toLocaleLowerCase());
  if (condition.operator === "contains") return lower.some((item) => left.includes(item));
  if (condition.operator === "not_contains") return lower.every((item) => !left.includes(item));
  if (condition.operator === "equals") return lower.some((item) => left === item);
  if (condition.operator === "not_equals") return lower.every((item) => left !== item);
  return false;
}

export function filterRunRows(rows: RunSummary[], conditions: RunFilterCondition[]) {
  const active = conditions.filter((item) => {
    if (!operatorNeedsValue(item.operator)) return true;
    const values = Array.isArray(item.value) ? item.value : [item.value];
    return values.some((value) => String(value ?? "").trim());
  });
  return active.length ? rows.filter((row) => active.every((condition) => matches(row, condition))) : rows;
}

export function buildRunFilterValueOptions(rows: RunSummary[]): FilterValueOptions<RunFilterField> {
  return RUN_FILTER_FIELDS.reduce((all, field) => {
    if (field.kind !== "text") return all;
    const values = [...new Set(rows.map((row) => String(actual(row, field.value) ?? "")).filter(Boolean))];
    all[field.value] = values.map((value) => ({ value, label: value }));
    return all;
  }, {} as FilterValueOptions<RunFilterField>);
}
