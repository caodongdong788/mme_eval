import dayjs, { type Dayjs } from "dayjs";
import isoWeek from "dayjs/plugin/isoWeek";
import type { RunSummary } from "../api/types";
import { parseApiDateTime } from "./datetime";

dayjs.extend(isoWeek);

export type RunsDateRangeValue = [Dayjs, Dayjs];

export type RunsDatePresetKey = "this_week" | "this_month" | "this_year" | "last_7" | "last_30";

export interface RunsPeriodBounds {
  start: Dayjs;
  end: Dayjs;
}

export function getRunsDatePresetRange(key: RunsDatePresetKey): RunsDateRangeValue {
  const today = dayjs();
  switch (key) {
    case "this_week":
      return [today.startOf("isoWeek"), today];
    case "this_month":
      return [today.startOf("month"), today];
    case "this_year":
      return [today.startOf("year"), today];
    case "last_7":
      return [today.subtract(6, "day"), today];
    case "last_30":
      return [today.subtract(29, "day"), today];
  }
}

export const RUNS_DATE_QUICK_PRESETS: { key: RunsDatePresetKey; label: string }[] = [
  { key: "this_week", label: "本周" },
  { key: "this_month", label: "本月" },
  { key: "this_year", label: "今年" },
  { key: "last_7", label: "最近 7 天" },
  { key: "last_30", label: "最近 30 天" },
];

export const RUNS_DATE_PRESETS = RUNS_DATE_QUICK_PRESETS.map((p) => ({
  label: p.label,
  value: getRunsDatePresetRange(p.key),
}));

export function isSameDateRange(
  current: RunsDateRangeValue | null,
  preset: RunsDateRangeValue
): boolean {
  if (!current) return false;
  return current[0].isSame(preset[0], "day") && current[1].isSame(preset[1], "day");
}

export function toPeriodBounds(range: RunsDateRangeValue): RunsPeriodBounds {
  return { start: range[0].startOf("day"), end: range[1].endOf("day") };
}

/** 与当前周期等长的紧邻上一周期（按自然日、含首尾）。 */
export function previousPeriodBounds(bounds: RunsPeriodBounds): RunsPeriodBounds {
  const days = bounds.end.diff(bounds.start, "day") + 1;
  const prevEnd = bounds.start.subtract(1, "day").endOf("day");
  const prevStart = prevEnd.subtract(days - 1, "day").startOf("day");
  return { start: prevStart, end: prevEnd };
}

export function runCreatedAtMs(run: RunSummary): number | null {
  if (!run.created_at) return null;
  const t = parseApiDateTime(run.created_at).getTime();
  return Number.isNaN(t) ? null : t;
}

export function filterRunsByPeriod(
  runs: RunSummary[],
  bounds: RunsPeriodBounds
): RunSummary[] {
  return runs.filter((r) => {
    const t = runCreatedAtMs(r);
    if (t == null) return false;
    const d = dayjs(t);
    return !d.isBefore(bounds.start, "day") && !d.isAfter(bounds.end, "day");
  });
}

export function formatPeriodLabel(bounds: RunsPeriodBounds): string {
  const fmt = (d: Dayjs) => d.format("MM-DD");
  if (bounds.start.isSame(bounds.end, "day")) {
    return fmt(bounds.start);
  }
  return `${fmt(bounds.start)} ~ ${fmt(bounds.end)}`;
}
