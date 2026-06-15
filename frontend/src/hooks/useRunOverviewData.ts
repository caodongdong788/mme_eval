import { useMemo } from "react";
import { RunDetail } from "../api/index";
import { useFailureTagLabels } from "../failureTags";
import { DIM_LABEL } from "../labels";

export function useRunOverviewData(run: RunDetail) {
  const tagLabel = useFailureTagLabels();

  const levelData = useMemo(
    () =>
      Object.entries(run.by_level).map(([lvl, b]) => {
        const rate = b.total ? b.passed / b.total : 0;
        return {
          name: lvl,
          count: b.total,
          passed: b.passed,
          rate,
          ratePct: Number((rate * 100).toFixed(1)),
        };
      }),
    [run]
  );

  const dimData = useMemo(() => {
    const avg = (run.grading?.avg_dimension || {}) as Record<string, number>;
    return Object.entries(avg).map(([k, v]) => ({ name: DIM_LABEL[k] || k, value: Number(v) }));
  }, [run]);

  const tagData = useMemo(() => {
    const c = run.failure_tag_counter || {};
    return Object.entries(c).map(([k, v]) => ({ name: tagLabel(k), value: v as number }));
  }, [run, tagLabel]);

  return { levelData, dimData, tagData };
}
