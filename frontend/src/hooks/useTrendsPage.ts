import { useEffect, useMemo, useState } from "react";
import { api, selectableBenchmarks, TrendPoint } from "../api/index";
import { useAsyncData } from "./useAsyncData";

export function useTrendsPage() {
  const { data: benchmarks, loading: loadingBenchmarks } = useAsyncData(
    () => api.listBenchmarks().then(selectableBenchmarks),
    []
  );
  const [benchmarkId, setBenchmarkId] = useState<number | undefined>();

  useEffect(() => {
    if (benchmarks?.length && benchmarkId === undefined) {
      setBenchmarkId(benchmarks[0].id);
    }
  }, [benchmarks, benchmarkId]);

  const { data: points, loading: loadingTrends } = useAsyncData(
    () =>
      benchmarkId != null
        ? api.getTrends(benchmarkId).then((d) => d.points)
        : Promise.resolve([] as TrendPoint[]),
    [benchmarkId]
  );

  const chartData = useMemo(
    () =>
      (points ?? []).map((p) => {
        const ci = p.pass_rate_ci || {};
        const rate = p.pass_rate * 100;
        const ciErr =
          ci.low != null && ci.high != null
            ? [Number((rate - ci.low * 100).toFixed(1)), Number((ci.high * 100 - rate).toFixed(1))]
            : undefined;
        return {
          name: p.name || p.run_slug,
          通过率: Number(rate.toFixed(1)),
          通过率CI: ciErr,
          综合分: p.avg_composite != null ? Number((p.avg_composite * 100).toFixed(1)) : null,
        };
      }),
    [points]
  );

  return {
    benchmarks: benchmarks ?? [],
    benchmarkId,
    setBenchmarkId,
    chartData,
    loading: loadingBenchmarks || loadingTrends,
  };
}
