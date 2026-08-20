import { useEffect, useState } from "react";
import { api, type AttributionTask, type CaseAttribution } from "../api";
import { formatApiError } from "../utils/apiError";

export function useAttributionCaseDetail(
  runId: number,
  taskId: number,
  sampleId: string
) {
  const [task, setTask] = useState<AttributionTask | null>(null);
  const [result, setResult] = useState<CaseAttribution | null>(null);
  const [error, setError] = useState<string>();

  useEffect(() => {
    let current = true;
    setError(undefined);
    setTask(null);
    setResult(null);
    Promise.all([
      api.getAttributionTask(runId, taskId),
      api.getAttributionTaskResult(runId, taskId, sampleId),
    ])
      .then(([nextTask, nextResult]) => {
        if (!current) return;
        setTask(nextTask);
        setResult(nextResult);
      })
      .catch((reason) => {
        if (current) setError(formatApiError(reason, "加载归因结果失败"));
      });
    return () => {
      current = false;
    };
  }, [runId, sampleId, taskId]);

  return { task, result, error };
}
