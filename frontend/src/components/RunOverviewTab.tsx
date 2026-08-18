import { useEffect, useMemo, useState } from "react";
import {
  api,
  ReviewStats,
  RunAttributionCategoryStats,
  RunDetail,
} from "../api/index";
import { useFailureTagLabels } from "../hooks/useConfigLabelMap";
import { DIM_LABEL } from "../labels";
import { buildCaseTypeOutcomeData } from "../utils/caseTypeMetrics";
import { buildDimensionScoreData } from "../utils/dimensionScores";
import { RunOverviewCharts } from "./RunOverviewCharts";
import { RunAttributionCategoryCharts } from "./RunAttributionCategoryCharts";
import { RunOverviewKpiGrid } from "./RunOverviewKpiGrid";
import { RunOverviewMetricsPanel } from "./RunOverviewMetricsPanel";

export function RunOverviewTab({
  run,
  reviewStats,
}: {
  run: RunDetail;
  reviewStats: ReviewStats | null;
}) {
  const tagLabel = useFailureTagLabels();
  const [attributionStats, setAttributionStats] =
    useState<RunAttributionCategoryStats | null>(null);
  const [attributionStatsLoading, setAttributionStatsLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setAttributionStatsLoading(true);
    api.getAttributionCategoryStats(run.id)
      .then((value) => {
        if (active) setAttributionStats(value);
      })
      .catch(() => {
        if (active) setAttributionStats(null);
      })
      .finally(() => {
        if (active) setAttributionStatsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [run.id]);

  const levelData = useMemo(
    () =>
      Object.entries(run.by_level).map(([lvl, b]) => {
        const rate = b.total ? b.passed / b.total : 0;
        return {
          name: lvl,
          count: b.total,
          passed: b.passed,
          rate,
          ratePct: Number((rate * 100).toFixed(1)),
        };
      }),
    [run]
  );

  const dimData = useMemo(() => {
    const avg = (run.grading?.avg_dimension || {}) as Record<string, unknown>;
    return buildDimensionScoreData(avg, DIM_LABEL);
  }, [run]);

  const tagData = useMemo(() => {
    const c = run.failure_tag_counter || {};
    return Object.entries(c).map(([k, v]) => ({
      name: tagLabel(k),
      value: v as number,
    }));
  }, [run, tagLabel]);

  const caseTypeData = useMemo(
    () => buildCaseTypeOutcomeData(run.by_case_type),
    [run.by_case_type]
  );

  return (
    <div className="run-overview-page">
      <RunOverviewKpiGrid run={run} reviewStats={reviewStats} />
      <RunOverviewMetricsPanel run={run} />
      <RunAttributionCategoryCharts
        stats={attributionStats}
        loading={attributionStatsLoading}
      />
      <RunOverviewCharts
        caseTypeData={caseTypeData}
        levelData={levelData}
        dimData={dimData}
        tagData={tagData}
      />
    </div>
  );
}
