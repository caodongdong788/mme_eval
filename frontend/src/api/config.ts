import { http } from "./client";
import type { EvaluationAccountsConfig, EvaluationStandard, JudgeDefaults, OpenApiAccessKey, OpenApiPermission } from "./types";

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
  listOpenApiKeys: () =>
    http.get<OpenApiAccessKey[]>("/config/open-api-keys").then((r) => r.data),
  createOpenApiKey: (payload: { name: string; permissions: OpenApiPermission[] }) =>
    http.post<OpenApiAccessKey>("/config/open-api-keys", payload).then((r) => r.data),
  updateOpenApiKey: (id: number, payload: { name: string; permissions: OpenApiPermission[] }) =>
    http.patch<OpenApiAccessKey>(`/config/open-api-keys/${id}`, payload).then((r) => r.data),
  rotateOpenApiKey: (id: number) =>
    http.post<OpenApiAccessKey>(`/config/open-api-keys/${id}/rotate`).then((r) => r.data),
  deleteOpenApiKey: (id: number) => http.delete(`/config/open-api-keys/${id}`),
};
