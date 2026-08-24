import { useEffect, useMemo, useState } from "react";
import { api, type RunAttributionCategoryStats, type RunSummary } from "../api";
import {
  mergeAttributionCategoryStats,
  selectLatestAttributedRunsByBenchmark,
} from "../utils/latestAttributionCategoryStats";

/** 首页两个 Benchmark 最新归因结果的分类汇总。 */
export function useLatestAttributionCategoryStats(runs: RunSummary[]) {
  const [stats, setStats] = useState<RunAttributionCategoryStats | null>(null);
  const [loading, setLoading] = useState(false);
  const latestRunIdsKey = useMemo(
    () => selectLatestAttributedRunsByBenchmark(runs).map((run) => run.id).join(","),
    [runs],
  );

  useEffect(() => {
    let cancelled = false;
    const latestRunIds = latestRunIdsKey
      ? latestRunIdsKey.split(",").map((value) => Number(value))
      : [];
    if (latestRunIds.length === 0) {
      setStats(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);
    Promise.all(latestRunIds.map((runId) => api.getAttributionCategoryStats(runId)))
      .then((items) => {
        if (!cancelled) setStats(mergeAttributionCategoryStats(items));
      })
      // 后台刷新失败时保留上一版图表，避免瞬间清空；下一次 Run ID
      // 变化后仍会再次请求。
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [latestRunIdsKey]);

  return { stats, loading };
}
