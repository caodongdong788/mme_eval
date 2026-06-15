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
    <div className="ov-stack">
      <RunOverviewKpiGrid run={run} reviewStats={reviewStats} />
      <div className="ov-rule" />
      <RunOverviewMetricsPanel run={run} />
      <div className="ov-rule" />
      <RunOverviewCharts levelData={levelData} dimData={dimData} tagData={tagData} />
    </div>
  );
}
