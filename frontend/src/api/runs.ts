import { http } from "./client";
import type {
  AnnotatePayload,
  Annotation,
  CaseRow,
  CasesYaml,
  PreviewRejudgePayload,
  PreviewRejudgeResult,
  ProgressInfo,
  RejudgePayload,
  ReviewQueueItem,
  ReviewStats,
  RunCreatePayload,
  RunDetail,
  RunDiff,
  RunSummary,
} from "./types";

/** 用例列表单次拉取上限（当前 benchmark ≤92，与 LIST_LIMIT_MAX 对齐）。 */
export const CASE_LIST_LIMIT = 100;

export const runsApi = {
  listRuns: () => http.get<RunSummary[]>("/runs").then((r) => r.data),
  getRun: (id: number) => http.get<RunDetail>(`/runs/${id}`).then((r) => r.data),
  createRun: (payload: RunCreatePayload) =>
    http.post<RunSummary>("/runs", payload).then((r) => r.data),
  getProgress: (id: number) =>
    http.get<ProgressInfo>(`/runs/${id}/progress`).then((r) => r.data),
  listCaseResults: (id: number, params?: Record<string, any>) =>
    http.get<CaseRow[]>(`/runs/${id}/cases`, { params }).then((r) => r.data),
  getCaseDetail: (id: number, sampleId: string) =>
    http.get<any>(`/runs/${id}/cases/${sampleId}`).then((r) => r.data),
  getRunCasesYaml: (id: number, params?: Record<string, any>) =>
    http.get<CasesYaml>(`/runs/${id}/cases-yaml`, { params }).then((r) => r.data),
  previewRejudgeCase: (id: number, sampleId: string, payload?: PreviewRejudgePayload) =>
    http
      .post<PreviewRejudgeResult>(
        `/runs/${id}/cases/${sampleId}/preview-rejudge`,
        payload ?? {}
      )
      .then((r) => r.data),
  getReviewQueue: (id: number, params?: Record<string, any>) =>
    http.get<ReviewQueueItem[]>(`/runs/${id}/review-queue`, { params }).then((r) => r.data),
  getReviewStats: (id: number) =>
    http.get<ReviewStats>(`/runs/${id}/review-stats`).then((r) => r.data),
  getCaseAnnotations: (id: number, sampleId: string) =>
    http.get<Annotation[]>(`/runs/${id}/cases/${sampleId}/annotations`).then((r) => r.data),
  annotateCase: (id: number, sampleId: string, payload: AnnotatePayload) =>
    http.post<Annotation>(`/runs/${id}/cases/${sampleId}/annotate`, payload).then((r) => r.data),
  exportTranscripts: (id: number, params?: Record<string, any>) =>
    http
      .post<{ url: string; count: number; filename: string }>(
        `/runs/${id}/export-transcripts`,
        null,
        { params }
      )
      .then((r) => r.data),
  diffRun: (id: number, against: number) =>
    http.get<RunDiff>(`/runs/${id}/diff`, { params: { against } }).then((r) => r.data),
  deleteRun: (id: number) => http.delete(`/runs/${id}`).then((r) => r.data),
  rejudgeRun: (id: number, payload?: RejudgePayload) =>
    http.post<RunSummary>(`/runs/${id}/rejudge`, payload ?? null).then((r) => r.data),
  resumeRun: (id: number) =>
    http.post<RunSummary>(`/runs/${id}/resume`).then((r) => r.data),
  renameRun: (id: number, name: string) =>
    http.patch<RunSummary>(`/runs/${id}`, { name }).then((r) => r.data),
  setPin: (id: number, pinned: boolean) =>
    http
      .post<{ id: number; pinned: boolean }>(`/runs/${id}/pin`, null, {
        params: { pinned },
      })
      .then((r) => r.data),
};
