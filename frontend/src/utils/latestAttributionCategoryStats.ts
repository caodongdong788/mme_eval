import type {
  AttributionCategoryCount,
  RunAttributionCategoryStats,
  RunSummary,
} from "../api/types";

function evaluatedAt(run: RunSummary): number {
  const value = run.finished_at || run.created_at;
  const timestamp = value ? Date.parse(value) : Number.NaN;
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

/**
 * 首页只选每个 Benchmark 最新、且已有可用归因结果的评测。当前首页展示两个
 * Benchmark，因此按评测完成时间取最新的两组，避免同一 Benchmark 的历史 Run
 * 进入汇总。
 */
export function selectLatestAttributedRunsByBenchmark(
  runs: RunSummary[],
  benchmarkLimit = 2,
): RunSummary[] {
  const latestByBenchmark = new Map<number, RunSummary>();
  for (const run of runs) {
    if (
      run.status !== "success" ||
      run.benchmark_id == null ||
      typeof run.cx_agent_optimization_count !== "number" ||
      !Number.isFinite(run.cx_agent_optimization_count)
    ) {
      continue;
    }
    const current = latestByBenchmark.get(run.benchmark_id);
    if (
      !current ||
      evaluatedAt(run) > evaluatedAt(current) ||
      (evaluatedAt(run) === evaluatedAt(current) && run.id > current.id)
    ) {
      latestByBenchmark.set(run.benchmark_id, run);
    }
  }
  return [...latestByBenchmark.values()]
    .sort((left, right) => evaluatedAt(right) - evaluatedAt(left) || right.id - left.id)
    .slice(0, benchmarkLimit);
}

/**
 * 两个 Benchmark 的 Case 是独立样本集；这里保留各自已去重后的 Case 数并相加。
 * 同一 Benchmark 内的 Case/分类去重由后端单 Run 分类接口保证。
 */
export function mergeAttributionCategoryStats(
  statsItems: RunAttributionCategoryStats[],
): RunAttributionCategoryStats {
  const firstLevel = new Map<string, AttributionCategoryCount>();
  const secondLevel = new Map<string, AttributionCategoryCount>();
  let attributedCaseCount = 0;

  const mergeRows = (
    target: Map<string, AttributionCategoryCount>,
    rows: AttributionCategoryCount[],
  ) => {
    for (const row of rows) {
      const current = target.get(row.key);
      if (current) {
        current.case_count += row.case_count;
      } else {
        target.set(row.key, { ...row });
      }
    }
  };

  for (const stats of statsItems) {
    attributedCaseCount += stats.attributed_case_count || 0;
    mergeRows(firstLevel, stats.first_level || []);
    mergeRows(secondLevel, stats.second_level || []);
  }
  const sortRows = (rows: AttributionCategoryCount[]) =>
    rows.sort((left, right) => right.case_count - left.case_count || left.label.localeCompare(right.label, "zh-CN"));
  return {
    attributed_case_count: attributedCaseCount,
    first_level: sortRows([...firstLevel.values()]),
    second_level: sortRows([...secondLevel.values()]),
  };
}
