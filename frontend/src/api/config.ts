import { http } from "./client";
import type { JudgeDefaults, ReleaseThresholdItem } from "./types";

export const configApi = {
  getReleaseThresholds: () =>
    http.get<ReleaseThresholdItem[]>("/config/release-thresholds").then((r) => r.data),
  putReleaseThresholds: (overrides: Record<string, number | null>) =>
    http
      .put<ReleaseThresholdItem[]>("/config/release-thresholds", { overrides })
      .then((r) => r.data),
  getFailureTagLabels: () =>
    http.get<Record<string, string>>(`/config/failure-tags`).then((r) => r.data),
  getJudgeVerdictLabels: () =>
    http.get<Record<string, string>>(`/config/judge-verdict-labels`).then((r) => r.data),
  getJudgeDefaults: () =>
    http.get<JudgeDefaults>("/config/judge-defaults").then((r) => r.data),
};
