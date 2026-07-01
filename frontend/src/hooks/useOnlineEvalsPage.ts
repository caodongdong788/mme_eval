import { Form, Modal, message } from "antd";
import { createElement, useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  type Benchmark,
  type JudgeModel,
  type OnlineEval,
  type OnlineEvalDetail,
  type OnlineEvalExportFilters,
  type ProgressInfo,
} from "../api/index";
import { formatApiError } from "../utils/apiError";
import { useAsyncData } from "./useAsyncData";

export interface OnlineEvalFormValues {
  name: string;
  benchmark_id: number;
  judge_model_id?: number;
  note?: string;
}

export const ONLINE_DIMENSIONS = [
  { key: "emotional_support", label: "情绪承接", max: 2.5 },
  { key: "actionability", label: "行动力", max: 2.5 },
  { key: "personalization", label: "个性化", max: 2.0 },
  { key: "professional_boundary", label: "专业准确性与边界", max: 2.0 },
  { key: "natural_personality", label: "自然表达与人格感", max: 1.0 },
] as const;

export function useOnlineEvalsPage() {
  const [form] = Form.useForm<OnlineEvalFormValues>();
  const [rows, setRows] = useState<OnlineEval[]>([]);
  const [loading, setLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [progress, setProgress] = useState<Record<number, ProgressInfo>>({});
  const reloadSeq = useRef(0);
  const { data: benchmarksData, error: benchmarksError } = useAsyncData(
    () => api.listBenchmarks(),
    [],
  );
  const { data: judgeModelsData, error: judgeModelsError } = useAsyncData(
    () => api.listJudgeModels(),
    [],
  );
  const [submitting, setSubmitting] = useState(false);
  const [detail, setDetail] = useState<OnlineEvalDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  const reload = useCallback(async (): Promise<boolean> => {
    const seq = ++reloadSeq.current;
    try {
      const list = await api.listOnlineEvals();
      if (seq !== reloadSeq.current) return false;

      setRows(list);
      setListError(null);
      const active = list.filter((row) => row.status === "pending" || row.status === "running");
      const entries = await Promise.all(
        active.map(async (row) => {
          try {
            return [row.id, await api.getOnlineEvalProgress(row.id)] as const;
          } catch {
            return [row.id, { status: row.status, progress: row.progress ?? null }] as const;
          }
        })
      );
      if (seq !== reloadSeq.current) return active.length > 0;

      setProgress(Object.fromEntries(entries));
      return active.length > 0;
    } catch (e: unknown) {
      if (seq === reloadSeq.current) {
        setListError(formatApiError(e, "加载线上评测失败"));
      }
      return false;
    }
  }, []);

  useEffect(() => {
    let stopped = false;
    setLoading(true);
    reload().finally(() => {
      if (!stopped) setLoading(false);
    });
    return () => {
      stopped = true;
    };
  }, [reload]);

  const hasActiveRows = rows.some((row) => row.status === "pending" || row.status === "running");
  useEffect(() => {
    if (!hasActiveRows) return undefined;
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void reload();
      }
    }, 3000);
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        void reload();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [hasActiveRows, reload]);

  const submit = async () => {
    const values = await form.validateFields();
    setSubmitting(true);
    try {
      const created = await api.createOnlineEval({
        name: values.name.trim(),
        note: values.note?.trim() || "",
        source_type: "benchmark",
        benchmark_id: values.benchmark_id,
        judge_model_id: values.judge_model_id ?? null,
      });
      setRows((prev) => [created, ...prev.filter((row) => row.id !== created.id)]);
      setProgress((prev) => ({
        ...prev,
        [created.id]: { status: created.status, progress: created.progress ?? null },
      }));
      message.success("线上评测已创建，正在后台评分");
      form.resetFields();
      void reload();
    } catch (e: unknown) {
      message.error(formatApiError(e, "创建线上评测失败"));
    } finally {
      setSubmitting(false);
    }
  };

  const openDetail = async (id: number) => {
    setDetailLoading(true);
    try {
      setDetail(await api.getOnlineEval(id));
    } catch (e: unknown) {
      message.error(formatApiError(e, "加载线上评测详情失败"));
    } finally {
      setDetailLoading(false);
    }
  };

  const deleteEval = async (id: number) => {
    ++reloadSeq.current;
    try {
      await api.deleteOnlineEval(id);
      setRows((prev) => prev.filter((row) => row.id !== id));
      setProgress((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      setDetail((prev) => (prev?.id === id ? null : prev));
      message.success("已删除线上评测记录");
    } catch (e: unknown) {
      message.error(formatApiError(e, "删除线上评测失败"));
      void reload();
    }
  };

  const exportDetailCases = async (filters: OnlineEvalExportFilters): Promise<boolean> => {
    if (!detail) return false;
    setExporting(true);
    try {
      const res = await api.exportOnlineEvalCases(detail.id, {
        ...filters,
        parent_folder_token: "",
      });
      Modal.success({
        title: "评测清单已导出到飞书",
        content: createElement(
          "span",
          null,
          `共 ${res.count} 条对话，文件名 ${res.filename}：`,
          createElement("br"),
          createElement(
            "a",
            { href: res.url, target: "_blank", rel: "noreferrer" },
            "点击打开飞书表格"
          )
        ),
      });
      return true;
    } catch (e: unknown) {
      message.error(formatApiError(e, "导出评测清单失败"));
      return false;
    } finally {
      setExporting(false);
    }
  };

  useEffect(() => {
    if (!detail) return undefined;
    const row = rows.find((item) => item.id === detail.id);
    const shouldRefresh =
      row &&
      (row.status !== detail.status ||
        (row.status === "success" && row.case_count !== detail.cases.length));
    if (!shouldRefresh) return undefined;

    let cancelled = false;
    api.getOnlineEval(detail.id)
      .then((next) => {
        if (!cancelled) setDetail(next);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [detail, rows]);

  return {
    form,
    rows,
    onlineBenchmarks: ((benchmarksData ?? []) as Benchmark[]).filter((b) => b.source === "online"),
    benchmarkNameById: Object.fromEntries(
      ((benchmarksData ?? []) as Benchmark[]).map((b) => [b.id, b.name])
    ) as Record<number, string>,
    judgeModels: (judgeModelsData ?? []) as JudgeModel[],
    loading,
    progress,
    loadError: listError ?? benchmarksError ?? judgeModelsError,
    reload,
    submitting,
    submit,
    detail,
    detailLoading,
    exporting,
    openDetail,
    exportDetailCases,
    deleteEval,
    closeDetail: () => setDetail(null),
  };
}
