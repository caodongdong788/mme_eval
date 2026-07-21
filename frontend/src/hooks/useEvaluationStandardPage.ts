import { api } from "../api";
import { useAsyncData } from "./useAsyncData";

export function useEvaluationStandardPage() {
  return useAsyncData(
    () => api.getEvaluationStandard(),
    [],
    "评分标准加载失败"
  );
}
