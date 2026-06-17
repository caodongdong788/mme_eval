import { ReviewStats, RunDetail } from "../api/index";
import { useRunOverviewData } from "../hooks/useRunOverviewData";
import { RunOverviewCharts } from "./RunOverviewCharts";
import { RunOverviewKpiGrid } from "./RunOverviewKpiGrid";
import { RunOverviewMetricsPanel } from "./RunOverviewMetricsPanel";

export function RunOverviewTab({
  run,
  reviewStats,
}: {
  run: RunDetail;
  reviewStats: ReviewStats | null;
}) {
  const { levelData, dimData, tagData } = useRunOverviewData(run);

  return (
    <div className="run-overview-page">
      <RunOverviewKpiGrid run={run} reviewStats={reviewStats} />
      <RunOverviewMetricsPanel run={run} />
      <RunOverviewCharts levelData={levelData} dimData={dimData} tagData={tagData} />
    </div>
  );
}
