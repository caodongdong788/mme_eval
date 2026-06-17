import dayjs from "dayjs";
import { describe, expect, it } from "vitest";
import type { RunSummary } from "../api/types";
import {
  filterRunsByPeriod,
  formatPeriodLabel,
  getRunsDatePresetRange,
  previousPeriodBounds,
  toPeriodBounds,
} from "./runsDateRange";

function run(partial: Partial<RunSummary> & { id: number; created_at: string }): RunSummary {
  return {
    run_slug: `run_${partial.id}`,
    name: `run_${partial.id}`,
    status: "success",
    adapter_type: "openai_compat",
    total: 10,
    passed: 8,
    pass_rate: 0.8,
    hard_gate_failed: 0,
    n_runs: 1,
    error_msg: "",
    has_traces: true,
    pinned: false,
    ...partial,
  };
}

describe("runsDateRange", () => {
  it("previousPeriodBounds mirrors inclusive day span", () => {
    const current = toPeriodBounds([dayjs("2026-06-10"), dayjs("2026-06-16")]);
    const prev = previousPeriodBounds(current);
    expect(prev.start.format("YYYY-MM-DD")).toBe("2026-06-03");
    expect(prev.end.format("YYYY-MM-DD")).toBe("2026-06-09");
  });

  it("filterRunsByPeriod keeps runs inside inclusive bounds", () => {
    const bounds = toPeriodBounds([dayjs("2026-06-10"), dayjs("2026-06-12")]);
    const runs = [
      run({ id: 1, created_at: "2026-06-09T12:00:00Z" }),
      run({ id: 2, created_at: "2026-06-10T08:00:00Z" }),
      run({ id: 3, created_at: "2026-06-12T10:00:00Z" }),
      run({ id: 4, created_at: "2026-06-13T01:00:00Z" }),
    ];
    expect(filterRunsByPeriod(runs, bounds).map((r) => r.id)).toEqual([2, 3]);
  });

  it("formatPeriodLabel renders single day or range", () => {
    const one = toPeriodBounds([dayjs("2026-06-10"), dayjs("2026-06-10")]);
    const range = toPeriodBounds([dayjs("2026-06-10"), dayjs("2026-06-16")]);
    expect(formatPeriodLabel(one)).toBe("06-10");
    expect(formatPeriodLabel(range)).toBe("06-10 ~ 06-16");
  });

  it("getRunsDatePresetRange covers quick keys", () => {
    const today = dayjs();
    const week = getRunsDatePresetRange("this_week");
    expect(week[0].isSame(today.startOf("isoWeek"), "day")).toBe(true);
    expect(week[1].isSame(today, "day")).toBe(true);
    const month = getRunsDatePresetRange("this_month");
    expect(month[0].isSame(today.startOf("month"), "day")).toBe(true);
  });
});
