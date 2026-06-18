import { http } from "./client";
import type { JudgeDefaults, ScoringProfileItem } from "./types";

export const configApi = {
  getScoringProfiles: () =>
    http.get<ScoringProfileItem[]>("/config/scoring-profiles").then((r) => r.data),
  putScoringProfiles: (overrides: Record<string, Record<string, unknown> | null>) =>
    http
      .put<ScoringProfileItem[]>("/config/scoring-profiles", { overrides })
      .then((r) => r.data),
  getFailureTagLabels: () =>
    http.get<Record<string, string>>(`/config/failure-tags`).then((r) => r.data),
  getJudgeVerdictLabels: () =>
    http.get<Record<string, string>>(`/config/judge-verdict-labels`).then((r) => r.data),
  getJudgeDefaults: () =>
    http.get<JudgeDefaults>("/config/judge-defaults").then((r) => r.data),
};
