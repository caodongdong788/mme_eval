import { http } from "./client";
import type { RunsOverviewMetrics, TrendPoint } from "./types";

export const dashboardApi = {
  getTrends: (benchmarkId: number) =>
    http
      .get<{ benchmark_id: number; points: TrendPoint[] }>("/dashboard/trends", {
        params: { benchmark_id: benchmarkId },
      })
      .then((r) => r.data),
  getRegressionTrends: (scheduledEvaluationId: number) =>
    http
      .get<{ scheduled_evaluation: { id: number; name: string; benchmark_id: number }; points: TrendPoint[] }>(
        "/dashboard/regression-trends",
        { params: { scheduled_evaluation_id: scheduledEvaluationId } }
      )
      .then((r) => r.data),
  getRunsOverviewMetrics: (runIds: number[]) =>
    http
      .post<RunsOverviewMetrics>("/dashboard/runs/metrics", { run_ids: runIds })
      .then((r) => r.data),
};
