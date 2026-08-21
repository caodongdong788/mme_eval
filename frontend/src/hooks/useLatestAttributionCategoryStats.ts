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
  const latestRuns = useMemo(() => selectLatestAttributedRunsByBenchmark(runs), [runs]);

  useEffect(() => {
    let cancelled = false;
    if (latestRuns.length === 0) {
      setStats(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);
    Promise.all(latestRuns.map((run) => api.getAttributionCategoryStats(run.id)))
      .then((items) => {
        if (!cancelled) setStats(mergeAttributionCategoryStats(items));
      })
      .catch(() => {
        if (!cancelled) setStats(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [latestRuns]);

  return { stats, loading };
}
