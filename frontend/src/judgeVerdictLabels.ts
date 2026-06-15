import { api } from "./api/index";
import { useConfigLabelMap } from "./hooks/useConfigLabelMap";
import { fallbackJudgeLabel } from "./utils/caseJudging";

const CACHE_KEY = "judge-verdict";
const fetchJudgeVerdictLabels = () => api.getJudgeVerdictLabels();

/** Judge verdict 全名 → 中文标签；未知值回退 fallbackJudgeLabel。 */
export function useJudgeVerdictLabels(): (name: string | undefined) => string {
  const resolve = useConfigLabelMap(
    CACHE_KEY,
    fetchJudgeVerdictLabels,
    (labels, name) => labels[name] || fallbackJudgeLabel(name)
  );
  return (name: string | undefined) => {
    if (!name) return "-";
    return resolve(name);
  };
}
