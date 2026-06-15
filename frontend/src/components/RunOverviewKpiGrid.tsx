import { ReviewStats, RunDetail } from "../api/index";
import { KpiTile } from "./KpiTile";

export function RunOverviewKpiGrid({
  run,
  reviewStats,
}: {
  run: RunDetail;
  reviewStats: ReviewStats | null;
}) {
  const sd = run.stability_distribution || {};

  return (
    <div className="kpi-grid">
      <KpiTile label="平均综合分" value={(run.grading?.avg_composite ?? 0).toFixed?.(3) ?? "-"} />
      <KpiTile
        label="通过率"
        value={`${(run.pass_rate * 100).toFixed(1)}%`}
        sub={
          run.pass_rate_ci && run.pass_rate_ci.low != null
            ? `${Math.round((run.pass_rate_ci.confidence ?? 0.95) * 100)}% CI ${(
                run.pass_rate_ci.low * 100
              ).toFixed(1)}–${(run.pass_rate_ci.high * 100).toFixed(1)}%`
            : undefined
        }
      />
      <KpiTile label="硬门槛失败" value={run.hard_gate_failed} emphasize={run.hard_gate_failed > 0} />
      <KpiTile label="总用例" value={run.total} />
      <KpiTile
        label={`稳定性 (N=${run.n_runs})`}
        value={`${sd.stable_pass || 0}/${sd.flaky || 0}/${sd.stable_fail || 0}`}
        sub="稳过 / 抖动 / 稳挂"
      />
      {reviewStats && reviewStats.queue_total > 0 && (
        <KpiTile
          label="待审 / 队列"
          value={`${reviewStats.pending}/${reviewStats.queue_total}`}
          sub={`人审通过率 ${(reviewStats.agree_rate * 100).toFixed(0)}%`}
        />
      )}
    </div>
  );
}
