import { useCallback, useEffect, useRef, useState } from "react";
import { message } from "antd";
import { api, ProgressInfo, RunSummary } from "../api/index";
import { formatApiError } from "../utils/apiError";
import { usePollingTask } from "./usePollingTask";

export function useRunsList() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<Record<number, ProgressInfo>>({});
  const reloadSeq = useRef(0);

  const reload = useCallback(async (): Promise<boolean> => {
    const seq = ++reloadSeq.current;
    const list = await api.listRuns();
    if (seq !== reloadSeq.current) return false;

    setRuns(list);
    const active = list.filter((r) => r.status === "running" || r.status === "pending");
    const entries = await Promise.all(
      active.map(async (r) => {
        try {
          return [r.id, await api.getProgress(r.id)] as const;
        } catch {
          return null;
        }
      })
    );
    if (seq !== reloadSeq.current) return active.length > 0;

    setProgress(
      Object.fromEntries(
        entries.filter((e): e is readonly [number, ProgressInfo] => e !== null)
      )
    );
    return active.length > 0;
  }, []);

  useEffect(() => {
    setLoading(true);
    void reload().finally(() => setLoading(false));
  }, [reload]);

  const anyActive = runs.some(
    (run) => run.status === "running" || run.status === "pending"
  );
  usePollingTask(
    async () => {
      await reload();
    },
    [reload],
    { enabled: anyActive, intervalMs: 3000 }
  );

  const onDelete = async (id: number) => {
    // 作废进行中的轮询 reload，避免其迟到的 listRuns 响应把已删行写回表格。
    ++reloadSeq.current;
    try {
      await api.deleteRun(id);
      setRuns((prev) => prev.filter((r) => r.id !== id));
      setProgress((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      message.success("已删除");
    } catch (e: unknown) {
      message.error(formatApiError(e, "删除失败"));
      await reload();
    }
  };

  return { runs, loading, progress, reload, onDelete };
}
