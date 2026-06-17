import type { RunSummary } from "../api/types";

export type RunsListFilter = "all" | "success" | "running" | "failed" | "pinned";

export interface RunsListKpis {
  total: number;
  avgPassPct: number | null;
  hardGateTotal: number;
  activeCount: number;
  successCount: number;
}

export interface RunsTrendPoint {
  label: string;
  passPct: number;
  runId: number;
  name: string;
}

const SUCCESS = "success";
const RUNNING = new Set(["running", "pending"]);

export function filterRuns(runs: RunSummary[], filter: RunsListFilter): RunSummary[] {
  switch (filter) {
    case "success":
      return runs.filter((r) => r.status === SUCCESS);
    case "running":
      return runs.filter((r) => RUNNING.has(r.status));
    case "failed":
      return runs.filter((r) => r.status === "failed");
    case "pinned":
      return runs.filter((r) => r.pinned);
    default:
      return runs;
  }
}

export function countRunsByFilter(runs: RunSummary[]): Record<RunsListFilter, number> {
  return {
    all: runs.length,
    success: filterRuns(runs, "success").length,
    running: filterRuns(runs, "running").length,
    failed: filterRuns(runs, "failed").length,
    pinned: filterRuns(runs, "pinned").length,
  };
}

export function computeRunsListKpis(runs: RunSummary[]): RunsListKpis {
  const successRuns = runs.filter((r) => r.status === SUCCESS);
  const avgPassPct =
    successRuns.length > 0
      ? Math.round((successRuns.reduce((s, r) => s + r.pass_rate, 0) / successRuns.length) * 1000) / 10
      : null;
  return {
    total: runs.length,
    avgPassPct,
    hardGateTotal: successRuns.reduce((s, r) => s + (r.hard_gate_failed || 0), 0),
    activeCount: runs.filter((r) => RUNNING.has(r.status)).length,
    successCount: successRuns.length,
  };
}

function sortByCreatedDesc(runs: RunSummary[]): RunSummary[] {
  return [...runs].sort((a, b) => {
    const ta = a.created_at ? Date.parse(a.created_at) : 0;
    const tb = b.created_at ? Date.parse(b.created_at) : 0;
    return tb - ta;
  });
}

export function buildPassRateTrend(runs: RunSummary[], limit = 7): RunsTrendPoint[] {
  const success = sortByCreatedDesc(runs.filter((r) => r.status === SUCCESS)).slice(0, limit);
  return success
    .reverse()
    .map((r) => {
      const d = r.created_at ? new Date(r.created_at) : null;
      const label =
        d && !Number.isNaN(d.getTime())
          ? `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
          : `#${r.id}`;
      return {
        label,
        passPct: Math.round(r.pass_rate * 1000) / 10,
        runId: r.id,
        name: r.name || r.run_slug,
      };
    });
}

export function buildStatusDistribution(runs: RunSummary[]): Array<{ name: string; value: number }> {
  const counts: Record<string, number> = {
    已完成: 0,
    进行中: 0,
    失败: 0,
    其他: 0,
  };
  for (const r of runs) {
    if (r.status === SUCCESS) counts["已完成"] += 1;
    else if (RUNNING.has(r.status)) counts["进行中"] += 1;
    else if (r.status === "failed") counts["失败"] += 1;
    else counts["其他"] += 1;
  }
  return Object.entries(counts)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }));
}

export function buildRecentPassBars(
  runs: RunSummary[],
  limit = 5
): Array<{ name: string; passPct: number }> {
  return sortByCreatedDesc(runs.filter((r) => r.status === SUCCESS))
    .slice(0, limit)
    .reverse()
    .map((r) => ({
      name: (r.name || r.run_slug).slice(0, 12),
      passPct: Math.round(r.pass_rate * 1000) / 10,
    }));
}

/** 当前周期 vs 等长上一周期的 KPI 差值；通过率单位为百分点。 */
export interface RunsPeriodDeltas {
  total: number;
  passRatePct: number | null;
  hardGate: number;
  active: number;
}

export function computeRunsPeriodDeltas(
  current: RunSummary[],
  previous: RunSummary[]
): RunsPeriodDeltas | null {
  if (current.length === 0 && previous.length === 0) return null;
  const cur = computeRunsListKpis(current);
  const prev = computeRunsListKpis(previous);
  let passRatePct: number | null = null;
  if (cur.avgPassPct != null && prev.avgPassPct != null) {
    passRatePct = Math.round((cur.avgPassPct - prev.avgPassPct) * 10) / 10;
  }
  return {
    total: cur.total - prev.total,
    passRatePct,
    hardGate: cur.hardGateTotal - prev.hardGateTotal,
    active: cur.activeCount - prev.activeCount,
  };
}
