import { api } from "./api/index";
import { useConfigLabelMap } from "./hooks/useConfigLabelMap";

const CACHE_KEY = "failure-tags";
const fetchFailureTagLabels = () => api.getFailureTagLabels();

/** 失败标签英文枚举值 → 中文短标签；未知值回退原值。 */
export function useFailureTagLabels(): (tag: string) => string {
  return useConfigLabelMap(CACHE_KEY, fetchFailureTagLabels, (labels, tag) => labels[tag] || tag);
}
