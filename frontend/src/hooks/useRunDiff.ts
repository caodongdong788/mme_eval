import { useEffect, useState } from "react";
import { message } from "antd";
import { api, RunDiff, RunSummary } from "../api/index";
import { formatApiError } from "../utils/apiError";

export function useRunDiff(runId: number, onBaselineSelected?: () => void) {
  const [otherRuns, setOtherRuns] = useState<RunSummary[]>([]);
  const [diff, setDiff] = useState<RunDiff | null>(null);
  const [diffBaselineId, setDiffBaselineId] = useState<number | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  useEffect(() => {
    api
      .listRuns()
      .then((rs) =>
        setOtherRuns(rs.filter((r) => r.id !== runId && r.status === "success"))
      );
  }, [runId]);

  const selectDiffBaseline = async (againstId: number) => {
    setDiffBaselineId(againstId);
    setDiffLoading(true);
    onBaselineSelected?.();
    try {
      const diffResult = await api.diffRun(runId, againstId);
      setDiff(diffResult);
    } catch (e: unknown) {
      setDiff(null);
      message.error(formatApiError(e, "加载对比数据失败"));
    } finally {
      setDiffLoading(false);
    }
  };

  return {
    otherRuns,
    diff,
    diffBaselineId,
    diffLoading,
    selectDiffBaseline,
  };
}
