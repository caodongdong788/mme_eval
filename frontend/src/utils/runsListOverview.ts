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
  timestamp: number;
  passPct: number;
  passed: number;
  total: number;
}

export interface PassRateTrend {
  points: RunsTrendPoint[];
  dateTicks: number[];
  xDomain: [number, number] | null;
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

/** 当前周期与等长上一周期的 cx-agent 优化点差值。 */
export interface CxAgentOptimizationPeriodDeltas {
  total: number | null;
  p0Total: number | null;
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
  const passRatePoints = buildDailyPassRatePoints(successRuns);
  const avgPassPct = aggregateDailyPassRatePct(passRatePoints);
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

type CompletedBenchmarkRun = RunSummary & { benchmark_id: number };

function isCompletedBenchmarkRun(run: RunSummary): run is CompletedBenchmarkRun {
  return (
    run.status === SUCCESS &&
    typeof run.benchmark_id === "number" &&
    Number.isFinite(run.benchmark_id) &&
    evaluationTimestamp(run) > 0
  );
}

function passRateBenchmarkIds(runs: RunSummary[]): number[] {
  return [...new Set(
    runs
      .filter(isCompletedBenchmarkRun)
      .map((run) => run.benchmark_id)
  )].sort((a, b) => a - b);
}

function aggregateDailyPassRatePct(points: RunsTrendPoint[]): number | null {
  const total = points.reduce((sum, point) => sum + point.total, 0);
  const passed = points.reduce((sum, point) => sum + point.passed, 0);
  return total > 0 ? Math.round((passed / total) * 1000) / 10 : null;
}

function buildDailyPassRatePoints(
  runs: RunSummary[],
  expectedBenchmarkIds = passRateBenchmarkIds(runs)
): RunsTrendPoint[] {
  const completed = runs.filter(isCompletedBenchmarkRun);
  if (expectedBenchmarkIds.length === 0) return [];

  const latestByDay = new Map<number, Map<number, (typeof completed)[number]>>();
  for (const run of completed) {
    const evaluatedAt = evaluationTimestamp(run);
    const day = dayStartTimestamp(evaluatedAt);
    const benchmarkRuns = latestByDay.get(day) || new Map();
    const existing = benchmarkRuns.get(run.benchmark_id);
    if (
      existing == null ||
      evaluatedAt > evaluationTimestamp(existing) ||
      (evaluatedAt === evaluationTimestamp(existing) && run.id > existing.id)
    ) {
      benchmarkRuns.set(run.benchmark_id, run);
    }
    latestByDay.set(day, benchmarkRuns);
  }

  return [...latestByDay.entries()]
    .filter(([, benchmarkRuns]) =>
      expectedBenchmarkIds.every((benchmarkId) => benchmarkRuns.has(benchmarkId))
    )
    .sort(([dayA], [dayB]) => dayA - dayB)
    .flatMap(([timestamp, benchmarkRuns]) => {
      const selected = expectedBenchmarkIds
        .map((benchmarkId) => benchmarkRuns.get(benchmarkId))
        .filter((run): run is (typeof completed)[number] => run != null);
      const total = selected.reduce((sum, run) => sum + Number(run.total || 0), 0);
      if (total <= 0) return [];
      const passed = selected.reduce((sum, run) => sum + Number(run.passed || 0), 0);
      const date = new Date(timestamp);
      return [{
        label: `${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`,
        timestamp,
        passPct: Math.round((passed / total) * 1000) / 10,
        passed,
        total,
      }];
    });
}

export function buildPassRateTrend(runs: RunSummary[], limit = 7): PassRateTrend {
  const benchmarkIds = passRateBenchmarkIds(runs);
  const allPoints = buildDailyPassRatePoints(runs, benchmarkIds);
  const points = allPoints.slice(-limit);
  const dateTicks = points.map((point) => point.timestamp);
  const xDomain = dateTicks.length
    ? [dateTicks[0], dateTicks[dateTicks.length - 1] + 24 * 60 * 60 * 1000 - 1] as [number, number]
    : null;
  return {
    points,
    dateTicks,
    xDomain,
  };
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

function isCompletedAttributedRun(
  run: RunSummary
): run is RunSummary & { cx_agent_optimization_count: number } {
  return (
    run.status === SUCCESS
    && typeof run.cx_agent_optimization_count === "number"
    && Number.isFinite(run.cx_agent_optimization_count)
    && evaluationTimestamp(run) > 0
  );
}

function attributionBenchmarkKey(run: RunSummary): string {
  return run.benchmark_id == null ? "unassigned" : String(run.benchmark_id);
}

function periodOptimizationAverage(
  runs: RunSummary[],
  expectedBenchmarkKeys: string[]
): { total: number; p0Total: number } | null {
  const completed = runs.filter(isCompletedAttributedRun);
  if (!completed.length || !expectedBenchmarkKeys.length) return null;

  const latestByDay = new Map<number, Map<string, (typeof completed)[number]>>();
  for (const run of completed) {
    const evaluatedAt = evaluationTimestamp(run);
    const day = dayStartTimestamp(evaluatedAt);
    const benchmarkRuns = latestByDay.get(day) || new Map();
    const key = attributionBenchmarkKey(run);
    const existing = benchmarkRuns.get(key);
    if (
      existing == null
      || evaluatedAt > evaluationTimestamp(existing)
      || (evaluatedAt === evaluationTimestamp(existing) && run.id > existing.id)
    ) {
      benchmarkRuns.set(key, run);
    }
    latestByDay.set(day, benchmarkRuns);
  }

  const dailyTotals = [...latestByDay.values()]
    .filter((benchmarkRuns) => expectedBenchmarkKeys.every((key) => benchmarkRuns.has(key)))
    .map((benchmarkRuns) => expectedBenchmarkKeys.reduce(
      (sum, key) => sum + Number(benchmarkRuns.get(key)?.cx_agent_optimization_count || 0),
      0
    ));
  const dailyP0Totals = [...latestByDay.values()]
    .filter((benchmarkRuns) => expectedBenchmarkKeys.every((key) => benchmarkRuns.has(key)))
    .map((benchmarkRuns) => expectedBenchmarkKeys.reduce(
      (sum, key) => sum + Number(benchmarkRuns.get(key)?.cx_agent_p0_optimization_count || 0),
      0
    ));
  if (!dailyTotals.length) return null;

  const average = (values: number[]) =>
    Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 10) / 10;
  return { total: average(dailyTotals), p0Total: average(dailyP0Totals) };
}

/**
 * 按与通过率趋势相同的口径比较：每个自然日仅取每个 Benchmark 最后一次
 * 已完成归因；只有两个周期均覆盖相同 Benchmark 时才计算环比，避免因样本
 * 集合变化把“新增/缺失 Benchmark”误当作优化点变化。
 */
export function computeCxAgentOptimizationPeriodDeltas(
  current: RunSummary[],
  previous: RunSummary[]
): CxAgentOptimizationPeriodDeltas | null {
  const attributed = [...current, ...previous].filter(isCompletedAttributedRun);
  const expectedBenchmarkKeys = [...new Set(attributed.map(attributionBenchmarkKey))].sort();
  if (!expectedBenchmarkKeys.length) return null;

  const currentAverage = periodOptimizationAverage(current, expectedBenchmarkKeys);
  const previousAverage = periodOptimizationAverage(previous, expectedBenchmarkKeys);
  if (!currentAverage || !previousAverage) return null;

  return {
    total: Math.round((currentAverage.total - previousAverage.total) * 10) / 10,
    p0Total: Math.round((currentAverage.p0Total - previousAverage.p0Total) * 10) / 10,
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
  const comparableBenchmarkIds = passRateBenchmarkIds([...current, ...previous]);
  const currentPassPct = aggregateDailyPassRatePct(
    buildDailyPassRatePoints(current, comparableBenchmarkIds)
  );
  const previousPassPct = aggregateDailyPassRatePct(
    buildDailyPassRatePoints(previous, comparableBenchmarkIds)
  );
  if (currentPassPct != null && previousPassPct != null) {
    passRatePct = Math.round((currentPassPct - previousPassPct) * 10) / 10;
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
