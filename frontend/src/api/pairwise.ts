import { http } from "./client";
import type {
  PairwiseCalibratePayload,
  PairwiseCaseVerdict,
  PairwiseComparability,
  PairwiseComparison,
  PairwiseCreatePayload,
  PairwiseDetail,
} from "./types";

export const pairwiseApi = {
  precheckPairwise: (runAId: number, runBId: number) =>
    http
      .get<PairwiseComparability>("/compare/pairwise/precheck", {
        params: { run_a_id: runAId, run_b_id: runBId },
      })
      .then((r) => r.data),
  createPairwise: (payload: PairwiseCreatePayload) =>
    http.post<PairwiseComparison>("/compare/pairwise", payload).then((r) => r.data),
  listPairwise: (runId?: number) =>
    http
      .get<PairwiseComparison[]>("/compare/pairwise", {
        params: runId ? { run_id: runId } : undefined,
      })
      .then((r) => r.data),
  getPairwise: (id: number) =>
    http.get<PairwiseDetail>(`/compare/pairwise/${id}`).then((r) => r.data),
  updatePairwiseNote: (id: number, note: string) =>
    http.patch<PairwiseComparison>(`/compare/pairwise/${id}`, { note }).then((r) => r.data),
  deletePairwise: (id: number) =>
    http.delete(`/compare/pairwise/${id}`).then((r) => r.data),
  calibratePairwiseVerdict: (
    comparisonId: number,
    sampleId: string,
    payload: PairwiseCalibratePayload
  ) =>
    http
      .patch<PairwiseCaseVerdict>(
        `/compare/pairwise/${comparisonId}/cases/${encodeURIComponent(sampleId)}`,
        payload
      )
      .then((r) => r.data),
  resetPairwiseCalibration: (comparisonId: number, sampleId: string) =>
    http
      .delete<PairwiseCaseVerdict>(
        `/compare/pairwise/${comparisonId}/cases/${encodeURIComponent(sampleId)}`
      )
      .then((r) => r.data),
};
