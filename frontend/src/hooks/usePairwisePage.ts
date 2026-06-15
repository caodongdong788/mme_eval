import { useEffect, useMemo, useState } from "react";
import { message } from "antd";
import {
  api,
  type JudgeModel,
  type PairwiseComparability,
  type PairwiseComparison,
  type RunSummary,
} from "../api/index";
import { formatApiError } from "../utils/apiError";
import { useAsyncData } from "./useAsyncData";

export const PAIRWISE_SUBJECT_LABELS: Record<string, string> = {
  model: "被测模型",
  base_url: "服务地址",
  system_prompt: "系统提示",
  adapter_type: "适配器类型",
};

function runLabel(r: RunSummary): string {
  return `#${r.id} · ${r.name}`;
}

export function usePairwisePage() {
  const { data: runsRaw } = useAsyncData(() => api.listRuns(), []);
  const runs = useMemo(
    () => (runsRaw ?? []).filter((r) => r.status === "success"),
    [runsRaw]
  );
  const { data: judgeModelsData } = useAsyncData(() => api.listJudgeModels(), []);
  const judgeModels: JudgeModel[] = judgeModelsData ?? [];

  const { data: fetchedHistory, reload: loadHistory } = useAsyncData(
    () => api.listPairwise(),
    []
  );
  const [history, setHistory] = useState<PairwiseComparison[]>([]);
  useEffect(() => {
    if (fetchedHistory) setHistory(fetchedHistory);
  }, [fetchedHistory]);

  const [runA, setRunA] = useState<number>();
  const [runB, setRunB] = useState<number>();
  const [judgeId, setJudgeId] = useState<number>();
  const [scope, setScope] = useState<"all" | "divergent_only">("all");
  const [note, setNote] = useState("");
  const [check, setCheck] = useState<PairwiseComparability | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const anyRunning = history.some((h) => h.status === "running");
  useEffect(() => {
    if (!anyRunning) return;
    const t = window.setInterval(() => {
      if (document.visibilityState === "visible") loadHistory();
    }, 2500);
    return () => window.clearInterval(t);
  }, [anyRunning, loadHistory]);

  useEffect(() => {
    if (runA && runB && runA !== runB) {
      api.precheckPairwise(runA, runB).then(setCheck).catch(() => setCheck(null));
    } else {
      setCheck(null);
    }
  }, [runA, runB]);

  const runOptions = useMemo(
    () => runs.map((r) => ({ value: r.id, label: runLabel(r), disabled: !r.has_traces })),
    [runs]
  );

  const canSubmit = Boolean(runA && runB && judgeId && check?.comparable);
  const subjectDiff = check?.subject_diff || {};
  const diffKeys = Object.keys(subjectDiff);

  const onSubmit = async () => {
    if (!runA || !runB || !judgeId) return;
    setSubmitting(true);
    try {
      await api.createPairwise({
        run_a_id: runA,
        run_b_id: runB,
        judge_model_id: judgeId,
        scope,
        note: note.trim() || undefined,
      });
      message.success("已发起对比，进度见下方历史列表");
      setNote("");
      loadHistory();
    } catch (e: unknown) {
      message.error(formatApiError(e, "发起对比失败"));
    } finally {
      setSubmitting(false);
    }
  };

  const saveNote = async (id: number, value: string) => {
    const next = value.trim();
    try {
      await api.updatePairwiseNote(id, next);
      setHistory((h) => h.map((x) => (x.id === id ? { ...x, note: next } : x)));
    } catch (e: unknown) {
      message.error(formatApiError(e, "保存备注失败"));
    }
  };

  const onDelete = async (id: number) => {
    try {
      await api.deletePairwise(id);
      message.success("已删除该对比");
      setHistory((h) => h.filter((x) => x.id !== id));
    } catch (e: unknown) {
      message.error(formatApiError(e, "删除失败"));
    }
  };

  return {
    runs,
    judgeModels,
    history,
    runA,
    setRunA,
    runB,
    setRunB,
    judgeId,
    setJudgeId,
    scope,
    setScope,
    note,
    setNote,
    check,
    submitting,
    runOptions,
    canSubmit,
    subjectDiff,
    diffKeys,
    onSubmit,
    saveNote,
    onDelete,
  };
}
