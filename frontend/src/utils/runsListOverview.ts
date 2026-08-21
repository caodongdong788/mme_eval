import type { RunSummary } from "../api/types";

export type RunsListFilter = "all" | "success" | "running" | "failed" | "pinned";

export interface RunsListKpis {
  total: number;
  avgPassPct: number | null;
  avgComposite: number | null;
  medicalSafetyFailedTotal: number;
  successCount: number;
}

export interface RunsTrendPoint {
  label: string;
  passPct: number;
  runId: number;
  name: string;
}

export interface CxAgentOptimizationTrendSeries {
  key: string;
  benchmarkId: number | null;
  name: string;
  latest: number;
  previous: number | null;
  latestP0: number;
  previousP0: number | null;
}

export interface CxAgentOptimizationTrend {
  points: Array<
    {
      label: string;
      timestamp: number;
      name: string;
    } & Record<string, string | number>
  >;
  series: CxAgentOptimizationTrendSeries[];
  dateTicks: number[];
  xDomain: [number, number] | null;
  latestTotal: number | null;
  latestP0Total: number | null;
  previousP0Total: number | null;
  previousTotal: number | null;
  p0Delta: number | null;
  delta: number | null;
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
  const counts: Record<RunsListFilter, number> = {
    all: runs.length,
    success: 0,
    running: 0,
    failed: 0,
    pinned: 0,
  };
  for (const r of runs) {
    if (r.status === SUCCESS) counts.success += 1;
    if (RUNNING.has(r.status)) counts.running += 1;
    if (r.status === "failed") counts.failed += 1;
    if (r.pinned) counts.pinned += 1;
  }
  return counts;
}

export function computeRunsListKpis(runs: RunSummary[]): RunsListKpis {
  const successRuns = runs.filter((r) => r.status === SUCCESS);
  const scoredRuns = successRuns.filter(
    (r): r is RunSummary & { avg_composite: number } =>
      typeof r.avg_composite === "number" && Number.isFinite(r.avg_composite)
  );
  const avgPassPct =
    successRuns.length > 0
      ? Math.round((successRuns.reduce((s, r) => s + r.pass_rate, 0) / successRuns.length) * 1000) / 10
      : null;
  const avgComposite =
    scoredRuns.length > 0
      ? Math.round((scoredRuns.reduce((s, r) => s + r.avg_composite, 0) / scoredRuns.length) * 10) / 10
      : null;
  return {
    total: runs.length,
    avgPassPct,
    avgComposite,
    medicalSafetyFailedTotal: successRuns.reduce((s, r) => s + (r.medical_safety_failed || 0), 0),
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

function evaluationTimestamp(run: RunSummary): number {
  const value = run.finished_at || run.created_at;
  const timestamp = value ? Date.parse(value) : Number.NaN;
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function dayStartTimestamp(timestamp: number): number {
  const date = new Date(timestamp);
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
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

/**
 * 仅展示已有可用归因结果的已完成评测：空值代表尚未归因，不能误当作 0 个优化点。
 */
export function buildCxAgentOptimizationTrend(
  runs: RunSummary[],
  limit = 7
): CxAgentOptimizationTrend {
  const attributed = runs.filter(
    (run): run is RunSummary & { cx_agent_optimization_count: number } =>
      run.status === SUCCESS &&
      typeof run.cx_agent_optimization_count === "number" &&
      Number.isFinite(run.cx_agent_optimization_count)
  );
  const grouped = new Map<string, typeof attributed>();
  for (const run of attributed) {
    const groupKey = run.benchmark_id == null ? "unassigned" : String(run.benchmark_id);
    const group = grouped.get(groupKey) || [];
    group.push(run);
    grouped.set(groupKey, group);
  }

  const series = [...grouped.entries()]
    .map(([groupKey, group]) => {
      // 同一 Benchmark 在同一天多次评测时，仅保留当天最后完成的一次。
      const latestRunByDay = new Map<number, (typeof group)[number]>();
      for (const run of [...group].sort(
        (a, b) => evaluationTimestamp(b) - evaluationTimestamp(a)
      )) {
        const evaluatedAt = evaluationTimestamp(run);
        const day = evaluatedAt ? dayStartTimestamp(evaluatedAt) : -run.id;
        if (!latestRunByDay.has(day)) latestRunByDay.set(day, run);
      }
      const selected = [...latestRunByDay.values()]
        .sort((a, b) => evaluationTimestamp(a) - evaluationTimestamp(b))
        .slice(-limit);
      const last = selected[selected.length - 1];
      const previous = selected.length > 1 ? selected[selected.length - 2] : null;
      const benchmarkId = last?.benchmark_id ?? null;
      return {
        key: `benchmark_${groupKey}`,
        benchmarkId,
        name:
          last?.benchmark_name?.trim() ||
          (benchmarkId == null ? "未关联 Benchmark" : `Benchmark #${benchmarkId}`),
        latest: Number(last.cx_agent_optimization_count),
        previous: previous == null ? null : Number(previous.cx_agent_optimization_count),
        latestP0: Number(last.cx_agent_p0_optimization_count || 0),
        previousP0:
          previous == null ? null : Number(previous.cx_agent_p0_optimization_count || 0),
        runs: selected,
      };
    })
    .sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));

  const pointsByDay = new Map<string, {
    label: string;
    timestamp: number;
    name: string;
  } & Record<string, string | number>>();
  for (const item of series) {
    for (const run of item.runs) {
        const evaluatedAt = evaluationTimestamp(run);
        // 同一自然日的不同 Benchmark 应在同一条纵轴上比较；横轴不区分小时分钟。
        const timestamp = evaluatedAt ? dayStartTimestamp(evaluatedAt) : 0;
        const d = evaluatedAt ? new Date(evaluatedAt) : null;
        const label =
          d && !Number.isNaN(d.getTime())
            ? `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
            : `#${run.id}`;
        const pointKey = timestamp ? String(timestamp) : `unknown-${run.id}`;
        const point = pointsByDay.get(pointKey) || {
          label,
          timestamp,
          name: label,
        };
        point[item.key] = Number(run.cx_agent_optimization_count);
        point[`${item.key}__p0`] = Number(run.cx_agent_p0_optimization_count || 0);
        point[`${item.key}__run_name`] = run.name || run.run_slug;
        pointsByDay.set(pointKey, point);
    }
  }
  const points = [...pointsByDay.values()].sort((a, b) => a.timestamp - b.timestamp);
  const dateTicks = [...new Set(
    points
      .map((point) => point.timestamp)
      .filter((timestamp) => timestamp > 0)
  )].sort((a, b) => a - b);
  const xDomain = dateTicks.length
    ? [dateTicks[0], dateTicks[dateTicks.length - 1] + 24 * 60 * 60 * 1000 - 1] as [number, number]
    : null;
  const publicSeries = series.map((item) => ({
    key: item.key,
    benchmarkId: item.benchmarkId,
    name: item.name,
    latest: item.latest,
    previous: item.previous,
    latestP0: item.latestP0,
    previousP0: item.previousP0,
  }));
  // 顶部指标仅比较同一日期内两个 Benchmark 都已完成归因的结果，不能跨日期拼接。
  const completeDailyPoints = points.filter((point) =>
    publicSeries.every((item) => typeof point[item.key] === "number")
  );
  const latestPoint = completeDailyPoints.length
    ? completeDailyPoints[completeDailyPoints.length - 1]
    : undefined;
  const previousPoint = completeDailyPoints.length > 1
    ? completeDailyPoints[completeDailyPoints.length - 2]
    : undefined;
  const sumPoint = (point: (typeof points)[number], suffix = "") =>
    publicSeries.reduce((sum, item) => sum + Number(point[`${item.key}${suffix}`] || 0), 0);
  const latestTotal = latestPoint ? sumPoint(latestPoint) : null;
  const latestP0Total = latestPoint ? sumPoint(latestPoint, "__p0") : null;
  const previousTotal = previousPoint ? sumPoint(previousPoint) : null;
  const previousP0Total = previousPoint ? sumPoint(previousPoint, "__p0") : null;
  return {
    points,
    series: publicSeries,
    dateTicks,
    xDomain,
    latestTotal,
    latestP0Total,
    previousTotal,
    previousP0Total,
    p0Delta:
      latestP0Total != null && previousP0Total != null
        ? latestP0Total - previousP0Total
        : null,
    delta:
      latestTotal != null && previousTotal != null ? latestTotal - previousTotal : null,
  };
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
  avgComposite: number | null;
  medicalSafetyFailed: number;
}

export function computeRunsPeriodDeltas(
  current: RunSummary[],
  previous: RunSummary[]
): RunsPeriodDeltas | null {
  if (current.length === 0 && previous.length === 0) return null;
  const cur = computeRunsListKpis(current);
  const prev = computeRunsListKpis(previous);
  let passRatePct: number | null = null;
  let avgComposite: number | null = null;
  if (cur.avgPassPct != null && prev.avgPassPct != null) {
    passRatePct = Math.round((cur.avgPassPct - prev.avgPassPct) * 10) / 10;
  }
  if (cur.avgComposite != null && prev.avgComposite != null) {
    avgComposite = Math.round((cur.avgComposite - prev.avgComposite) * 10) / 10;
  }
  return {
    total: cur.total - prev.total,
    passRatePct,
    avgComposite,
    medicalSafetyFailed: cur.medicalSafetyFailedTotal - prev.medicalSafetyFailedTotal,
  };
}
