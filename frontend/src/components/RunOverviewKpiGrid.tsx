import { ReviewStats, RunDetail } from "../api/index";
import { RunsKpi } from "./RunsKpi";

export function RunOverviewKpiGrid({
  run,
  reviewStats,
}: {
  run: RunDetail;
  reviewStats: ReviewStats | null;
}) {
  const sd = run.stability_distribution || {};
  const passSub =
    run.total > 0 || (run.pass_rate_ci && run.pass_rate_ci.low != null) ? (
      <>
        {run.total > 0 && (
          <span>
            通过 {run.passed} · 失败 {Math.max(0, run.total - run.passed)}
          </span>
        )}
        {run.pass_rate_ci && run.pass_rate_ci.low != null && (
          <span>
            {run.total > 0 && " · "}
            {Math.round((run.pass_rate_ci.confidence ?? 0.95) * 100)}% CI{" "}
            {(run.pass_rate_ci.low * 100).toFixed(1)}–{(run.pass_rate_ci.high * 100).toFixed(1)}%
          </span>
        )}
      </>
    ) : undefined;

  return (
    <div className="runs-kpi-row runs-kpi-row--overview">
      <RunsKpi title="平均综合分" value={(run.grading?.avg_composite ?? 0).toFixed?.(3) ?? "—"} />
      <RunsKpi
        title="通过率"
        tip="release_passed 口径"
        value={(run.pass_rate * 100).toFixed(1)}
        unit="%"
        sub={passSub}
      />
      <RunsKpi
        title="硬门槛失败"
        value={run.hard_gate_failed}
        unit="例"
        danger={run.hard_gate_failed > 0}
      />
      <RunsKpi title="总用例" value={run.total} unit="例" />
      <RunsKpi
        title={`稳定性 (N=${run.n_runs})`}
        tip="稳过 / 抖动 / 稳挂"
        value={`${sd.stable_pass || 0}/${sd.flaky || 0}/${sd.stable_fail || 0}`}
      />
      {reviewStats && reviewStats.queue_total > 0 ? (
        <RunsKpi
          title="待审 / 队列"
          value={`${reviewStats.pending}/${reviewStats.queue_total}`}
          sub={`人审通过率 ${(reviewStats.agree_rate * 100).toFixed(0)}%`}
        />
      ) : (
        <RunsKpi title="待审 / 队列" value="—" sub="无人审队列" />
      )}
    </div>
  );
}
