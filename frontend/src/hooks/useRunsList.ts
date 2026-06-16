import { useCallback, useEffect, useRef, useState } from "react";
import { message } from "antd";
import { api, ProgressInfo, RunSummary } from "../api/index";
import { formatApiError } from "../utils/apiError";

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
    let stopped = false;
    let timer: number | null = null;
    const clear = () => {
      if (timer !== null) {
        window.clearInterval(timer);
        timer = null;
      }
    };
    const schedule = (hasActive: boolean) => {
      clear();
      if (!hasActive || document.visibilityState !== "visible") return;
      timer = window.setInterval(async () => {
        if (document.visibilityState !== "visible") return;
        const stillActive = await reload();
        if (!stillActive) clear();
      }, 3000);
    };
    setLoading(true);
    reload()
      .then((hasActive) => {
        if (!stopped) schedule(hasActive);
      })
      .finally(() => setLoading(false));
    const onVisibility = async () => {
      if (document.visibilityState === "visible") {
        const hasActive = await reload();
        if (!stopped) schedule(hasActive);
      } else {
        clear();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stopped = true;
      clear();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [reload]);

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
