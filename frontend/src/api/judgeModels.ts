import { http } from "./client";
import type { JudgeModel, JudgeModelPayload } from "./types";

export const judgeModelsApi = {
  listJudgeModels: () => http.get<JudgeModel[]>("/judge-models").then((r) => r.data),
  getDefaultJudgePrompt: () =>
    http.get<{ prompt_template: string }>("/judge-models/default-prompt").then((r) => r.data),
  createJudgeModel: (payload: JudgeModelPayload) =>
    http.post<JudgeModel>("/judge-models", payload).then((r) => r.data),
  updateJudgeModel: (id: number, payload: JudgeModelPayload) =>
    http.patch<JudgeModel>(`/judge-models/${id}`, payload).then((r) => r.data),
  deleteJudgeModel: (id: number) => http.delete(`/judge-models/${id}`),
  optimizeJudgePrompt: (prompt: string) =>
    http
      .post<{ optimized_prompt: string }>("/judge-models/optimize-prompt", { prompt })
      .then((r) => r.data),
};
