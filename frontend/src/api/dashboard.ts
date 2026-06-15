import { http } from "./client";
import type { TrendPoint } from "./types";

export const dashboardApi = {
  getTrends: (benchmarkId: number) =>
    http
      .get<{ benchmark_id: number; points: TrendPoint[] }>("/dashboard/trends", {
        params: { benchmark_id: benchmarkId },
      })
      .then((r) => r.data),
};
