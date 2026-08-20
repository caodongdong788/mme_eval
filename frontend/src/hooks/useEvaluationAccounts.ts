import { api } from "../api";
import { useAsyncData } from "./useAsyncData";

export function useEvaluationAccounts(enabled = true) {
  return useAsyncData(
    () => api.getEvaluationAccounts(),
    [],
    "评测账号加载失败",
    { enabled },
  );
}
