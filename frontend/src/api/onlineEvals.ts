import { http } from "./client";
import type {
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
};
