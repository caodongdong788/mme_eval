import { http } from "./client";
import type {
  OnlineAnnotationPoolCase,
  OnlineAnnotationPoolCaseAddPayload,
  OnlineAnnotationPoolFeishuImportPayload,
  OnlineAnnotationPoolPath,
  OnlineAnnotationPoolPathCreatePayload,
  OnlineAnnotationPoolPathUpdatePayload,
  OnlineEval,
  OnlineEvalCreatePayload,
  OnlineEvalDetail,
  OnlineEvalExportFilters,
  OnlineEvalExportResult,
  ProgressInfo,
} from "./types";

function joinParam(values?: string[]): string | undefined {
  return values && values.length > 0 ? values.join(",") : undefined;
}

export const onlineEvalsApi = {
  createOnlineEval: (payload: OnlineEvalCreatePayload) =>
    http.post<OnlineEval>("/online-evals", payload).then((r) => r.data),
  listOnlineEvals: () => http.get<OnlineEval[]>("/online-evals").then((r) => r.data),
  getOnlineEval: (id: number) =>
    http.get<OnlineEvalDetail>(`/online-evals/${id}`).then((r) => r.data),
  getOnlineEvalProgress: (id: number) =>
    http.get<ProgressInfo>(`/online-evals/${id}/progress`).then((r) => r.data),
  exportOnlineEvalCases: (id: number, filters: OnlineEvalExportFilters) =>
    http
      .post<OnlineEvalExportResult>(`/online-evals/${id}/export-cases`, null, {
        params: {
          gate_status: joinParam(filters.gate_status),
          score_bucket: joinParam(filters.score_bucket),
          grade: joinParam(filters.grade),
          parent_folder_token: filters.parent_folder_token,
        },
      })
      .then((r) => r.data),
  deleteOnlineEval: (id: number) =>
    http.delete(`/online-evals/${id}`).then((r) => r.data),
  deleteOnlineEvalCase: (evalId: number, caseId: number) =>
    http.delete(`/online-evals/${evalId}/cases/${caseId}`).then((r) => r.data),
  rescoreOnlineEvalCase: (evalId: number, caseId: number) =>
    http
      .post<OnlineEvalDetail>(`/online-evals/${evalId}/cases/${caseId}/rescore`)
      .then((r) => r.data),
  listOnlineAnnotationPoolPaths: () =>
    http.get<OnlineAnnotationPoolPath[]>("/online-annotation-pool/paths").then((r) => r.data),
  createOnlineAnnotationPoolPath: (payload: OnlineAnnotationPoolPathCreatePayload) =>
    http.post<OnlineAnnotationPoolPath>("/online-annotation-pool/paths", payload).then((r) => r.data),
  importOnlineAnnotationPoolFromFeishu: (payload: OnlineAnnotationPoolFeishuImportPayload) =>
    http
      .post<OnlineAnnotationPoolPath>("/online-annotation-pool/paths/import-feishu", payload)
      .then((r) => r.data),
  updateOnlineAnnotationPoolPath: (pathId: number, payload: OnlineAnnotationPoolPathUpdatePayload) =>
    http
      .patch<OnlineAnnotationPoolPath>(`/online-annotation-pool/paths/${pathId}`, payload)
      .then((r) => r.data),
  deleteOnlineAnnotationPoolPath: (pathId: number) =>
    http.delete(`/online-annotation-pool/paths/${pathId}`).then((r) => r.data),
  addOnlineAnnotationPoolCase: (pathId: number, payload: OnlineAnnotationPoolCaseAddPayload) =>
    http
      .post<OnlineAnnotationPoolCase>(`/online-annotation-pool/paths/${pathId}/cases`, payload)
      .then((r) => r.data),
  listOnlineAnnotationPoolCases: (pathId: number) =>
    http
      .get<OnlineAnnotationPoolCase[]>(`/online-annotation-pool/paths/${pathId}/cases`)
      .then((r) => r.data),
  deleteOnlineAnnotationPoolCase: (pathId: number, caseId: number) =>
    http.delete(`/online-annotation-pool/paths/${pathId}/cases/${caseId}`).then((r) => r.data),
  exportOnlineAnnotationPoolPath: (pathId: number, parent_folder_token = "") =>
    http
      .post<OnlineEvalExportResult>(`/online-annotation-pool/paths/${pathId}/export-cases`, null, {
        params: { parent_folder_token },
      })
      .then((r) => r.data),
};
