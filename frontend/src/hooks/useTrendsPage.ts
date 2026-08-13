import { useEffect, useState } from "react";
import { api, selectableBenchmarks, TrendPoint } from "../api/index";
import { useAsyncData } from "./useAsyncData";

export function useTrendsPage() {
  const {
    data: benchmarks,
    loading: loadingBenchmarks,
    error: benchmarksError,
    reload: reloadBenchmarks,
  } = useAsyncData(() => api.listBenchmarks().then(selectableBenchmarks), []);
  const [benchmarkId, setBenchmarkId] = useState<number | undefined>();

  useEffect(() => {
    if (benchmarks?.length && benchmarkId === undefined) {
      setBenchmarkId(benchmarks[0].id);
    }
  }, [benchmarks, benchmarkId]);

  const {
    data: points,
    loading: loadingTrends,
    error: trendsError,
    reload: reloadTrends,
  } = useAsyncData(
    () =>
      benchmarkId != null
        ? api.getTrends(benchmarkId).then((d) => d.points)
        : Promise.resolve([] as TrendPoint[]),
    [benchmarkId]
  );

  const loadError = benchmarksError ?? (benchmarkId != null ? trendsError : null);
  const reload = () => {
    reloadBenchmarks();
    if (benchmarkId != null) reloadTrends();
  };

  return {
    benchmarks: benchmarks ?? [],
    benchmarkId,
    setBenchmarkId,
    points: points ?? [],
    loading: loadingBenchmarks || loadingTrends,
    loadError,
    reload,
  };
}
