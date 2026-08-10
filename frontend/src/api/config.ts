import { http } from "./client";
import type { EvaluationAccountsConfig, EvaluationStandard, JudgeDefaults, OpenApiKeyStatus } from "./types";

export const configApi = {
  getEvaluationStandard: () =>
    http.get<EvaluationStandard>("/config/evaluation-standard").then((r) => r.data),
  getFailureTagLabels: () =>
    http.get<Record<string, string>>(`/config/failure-tags`).then((r) => r.data),
  getJudgeVerdictLabels: () =>
    http.get<Record<string, string>>(`/config/judge-verdict-labels`).then((r) => r.data),
  getJudgeDefaults: () =>
    http.get<JudgeDefaults>("/config/judge-defaults").then((r) => r.data),
  getEvaluationAccounts: () =>
    http.get<EvaluationAccountsConfig>("/config/evaluation-accounts").then((r) => r.data),
  getOpenApiKeyStatus: () =>
    http.get<OpenApiKeyStatus>("/config/open-api-key").then((r) => r.data),
  updateOpenApiKey: (api_key: string) =>
    http.put<OpenApiKeyStatus>("/config/open-api-key", { api_key }).then((r) => r.data),
  clearOpenApiKey: () => http.delete("/config/open-api-key"),
};
