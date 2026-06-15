import { useCallback, useEffect, useState } from "react";
import { message } from "antd";
import { api, ProgressInfo, RunSummary } from "../api/index";
import { formatApiError } from "../utils/apiError";

export function useRunsList() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<Record<number, ProgressInfo>>({});

  const reload = useCallback(async (): Promise<boolean> => {
    const list = await api.listRuns();
    setRuns(list);
    const active = list.filter((r) => r.status === "running" || r.status === "pending");
    const entries = await Promise.all(
      active.map(async (r) => [r.id, await api.getProgress(r.id)] as const)
    );
    setProgress(Object.fromEntries(entries));
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
    try {
      await api.deleteRun(id);
      message.success("已删除");
      reload();
    } catch (e: unknown) {
      message.error(formatApiError(e, "删除失败"));
    }
  };

  return { runs, loading, progress, reload, onDelete };
}
