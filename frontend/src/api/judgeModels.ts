import { http } from "./client";
import type { JudgeModel, JudgeModelPayload } from "./types";

export const judgeModelsApi = {
  listJudgeModels: () => http.get<JudgeModel[]>("/judge-models").then((r) => r.data),
  createJudgeModel: (payload: JudgeModelPayload) =>
    http.post<JudgeModel>("/judge-models", payload).then((r) => r.data),
  updateJudgeModel: (id: number, payload: JudgeModelPayload) =>
    http.patch<JudgeModel>(`/judge-models/${id}`, payload).then((r) => r.data),
  deleteJudgeModel: (id: number) => http.delete(`/judge-models/${id}`),
};
