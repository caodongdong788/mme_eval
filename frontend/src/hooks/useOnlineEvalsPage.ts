import { Form, Modal, message } from "antd";
import { createElement, useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  type Benchmark,
  type JudgeModel,
  type OnlineAnnotationPoolCase,
  type OnlineAnnotationPoolPath,
  type OnlineEval,
  type OnlineEvalDetail,
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

export interface OnlineAnnotationPoolPathFormValues {
  path: string;
  description?: string;
  source_url?: string;
}

export const ONLINE_DIMENSIONS = [
  { key: "medical_safety", label: "医学安全性", role: "医生端", max: 5 },
  { key: "professional_accuracy", label: "专业准确性与边界", role: "医生端", max: 5 },
  { key: "clinical_inquiry", label: "临床追问充分性", role: "医生端", max: 5 },
  { key: "personalization", label: "个性化相关性", role: "护士端", max: 5 },
  { key: "plan_feasibility", label: "方案可行性与依从引导", role: "护士端", max: 5 },
  { key: "empathy", label: "被理解与共情", role: "患者端", max: 5 },
  { key: "executability", label: "可执行性", role: "患者端", max: 5 },
  { key: "communication", label: "沟通体验与继续意愿", role: "患者端", max: 5 },
] as const;

const MIN_RESCORE_PROGRESS_MS = 1200;

function delay(ms: number) {
  return new Promise<void>((resolve) => window.setTimeout(resolve, ms));
}

async function keepRescoreProgressVisible(startedAt: number) {
  const remain = MIN_RESCORE_PROGRESS_MS - (Date.now() - startedAt);
  if (remain > 0) {
    await delay(remain);
  }
}

export function useOnlineEvalsPage() {
  const [form] = Form.useForm<OnlineEvalFormValues>();
  const [poolPathForm] = Form.useForm<OnlineAnnotationPoolPathFormValues>();
  const [rows, setRows] = useState<OnlineEval[]>([]);
  const [loading, setLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [poolPaths, setPoolPaths] = useState<OnlineAnnotationPoolPath[]>([]);
  const [poolLoading, setPoolLoading] = useState(false);
  const [poolError, setPoolError] = useState<string | null>(null);
  const [poolSubmitting, setPoolSubmitting] = useState(false);
  const [poolImporting, setPoolImporting] = useState(false);
  const [poolAddingCaseId, setPoolAddingCaseId] = useState<number | null>(null);
  const [poolExportingPathId, setPoolExportingPathId] = useState<number | null>(null);
  const [poolUpdatingPathId, setPoolUpdatingPathId] = useState<number | null>(null);
  const [poolDeletingPathId, setPoolDeletingPathId] = useState<number | null>(null);
  const [poolEditingPath, setPoolEditingPath] = useState<OnlineAnnotationPoolPath | null>(null);
  const [poolDetailPath, setPoolDetailPath] = useState<OnlineAnnotationPoolPath | null>(null);
  const [poolDetailCases, setPoolDetailCases] = useState<OnlineAnnotationPoolCase[]>([]);
  const [poolDetailLoading, setPoolDetailLoading] = useState(false);
  const [poolDeletingCaseId, setPoolDeletingCaseId] = useState<number | null>(null);
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
  const [deletingCaseId, setDeletingCaseId] = useState<number | null>(null);
  const [rescoringCaseId, setRescoringCaseId] = useState<number | null>(null);

  const mergeDetailSummary = useCallback((next: OnlineEvalDetail) => {
    setRows((prev) =>
      prev.map((row) =>
        row.id === next.id
          ? {
              ...row,
              status: next.status,
              error_msg: next.error_msg,
              case_count: next.case_count,
              avg_score: next.avg_score,
              gate_fail_count: next.gate_fail_count,
              needs_review_count: next.needs_review_count,
              risk_tag_counter: next.risk_tag_counter,
              progress: next.progress,
              finished_at: next.finished_at,
            }
          : row
      )
    );
  }, []);

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

  const reloadPoolPaths = useCallback(async () => {
    setPoolLoading(true);
    try {
      setPoolPaths(await api.listOnlineAnnotationPoolPaths());
      setPoolError(null);
    } catch (e: unknown) {
      setPoolError(formatApiError(e, "加载标注池失败"));
    } finally {
      setPoolLoading(false);
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

  useEffect(() => {
    void reloadPoolPaths();
  }, [reloadPoolPaths]);

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
      const next = await api.getOnlineEval(id);
      setDetail(next);
      mergeDetailSummary(next);
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

  const deleteCase = async (evalId: number, caseId: number) => {
    setDeletingCaseId(caseId);
    try {
      await api.deleteOnlineEvalCase(evalId, caseId);
      const next = await api.getOnlineEval(evalId);
      setDetail(next);
      mergeDetailSummary(next);
      message.success("case 已删除");
    } catch (e: unknown) {
      message.error(formatApiError(e, "删除 case 失败"));
    } finally {
      setDeletingCaseId(null);
    }
  };

  const rescoreCase = async (evalId: number, caseId: number) => {
    const startedAt = Date.now();
    setRescoringCaseId(caseId);
    try {
      const next = await api.rescoreOnlineEvalCase(evalId, caseId);
      setDetail(next);
      mergeDetailSummary(next);
      await keepRescoreProgressVisible(startedAt);
      message.success("case 已重新评测");
    } catch (e: unknown) {
      await keepRescoreProgressVisible(startedAt);
      message.error(formatApiError(e, "重新评测 case 失败"));
    } finally {
      setRescoringCaseId(null);
    }
  };

  const createPoolPath = async () => {
    const values = await poolPathForm.validateFields();
    setPoolSubmitting(true);
    try {
      const created = await api.createOnlineAnnotationPoolPath({
        path: values.path.trim(),
        description: values.description?.trim() || "",
      });
      setPoolPaths((prev) => [created, ...prev.filter((item) => item.id !== created.id)]);
      poolPathForm.resetFields();
      message.success("标注集已创建");
    } catch (e: unknown) {
      message.error(formatApiError(e, "创建标注集失败"));
    } finally {
      setPoolSubmitting(false);
    }
  };

  const importPoolPathFromFeishu = async () => {
    const values = await poolPathForm.validateFields();
    const sourceUrl = values.source_url?.trim() || "";
    if (!sourceUrl) {
      message.error("请输入飞书表格 URL");
      return;
    }
    setPoolImporting(true);
    try {
      const imported = await api.importOnlineAnnotationPoolFromFeishu({
        path: values.path.trim(),
        description: values.description?.trim() || "",
        source_url: sourceUrl,
      });
      setPoolPaths((prev) => [imported, ...prev.filter((item) => item.id !== imported.id)]);
      poolPathForm.resetFields();
      message.success(`已从飞书导入 ${imported.case_count} 条 case`);
    } catch (e: unknown) {
      message.error(formatApiError(e, "飞书导入标注集失败"));
    } finally {
      setPoolImporting(false);
    }
  };

  const updatePoolPath = async (
    pathId: number,
    values: OnlineAnnotationPoolPathFormValues
  ) => {
    setPoolUpdatingPathId(pathId);
    try {
      const updated = await api.updateOnlineAnnotationPoolPath(pathId, {
        path: values.path.trim(),
        description: values.description?.trim() || "",
      });
      setPoolPaths((prev) =>
        prev.map((item) => (item.id === pathId ? updated : item))
      );
      setPoolDetailPath((prev) => (prev?.id === pathId ? updated : prev));
      message.success("标注集已更新");
      return true;
    } catch (e: unknown) {
      message.error(formatApiError(e, "更新标注集失败"));
      return false;
    } finally {
      setPoolUpdatingPathId(null);
    }
  };

  const addCaseToPool = async (caseId: number, pathId: number) => {
    setPoolAddingCaseId(caseId);
    try {
      await api.addOnlineAnnotationPoolCase(pathId, { online_eval_case_id: caseId });
      message.success("已加入标注池");
      void reloadPoolPaths();
    } catch (e: unknown) {
      message.error(formatApiError(e, "加入标注池失败"));
    } finally {
      setPoolAddingCaseId(null);
    }
  };

  const openPoolPathDetail = async (path: OnlineAnnotationPoolPath) => {
    setPoolDetailPath(path);
    setPoolDetailLoading(true);
    try {
      setPoolDetailCases(await api.listOnlineAnnotationPoolCases(path.id));
    } catch (e: unknown) {
      message.error(formatApiError(e, "加载标注集详情失败"));
      setPoolDetailCases([]);
    } finally {
      setPoolDetailLoading(false);
    }
  };

  const closePoolPathDetail = () => {
    setPoolDetailPath(null);
    setPoolDetailCases([]);
    setPoolDetailLoading(false);
    setPoolDeletingCaseId(null);
  };

  const deletePoolCase = async (pathId: number, caseId: number) => {
    setPoolDeletingCaseId(caseId);
    try {
      await api.deleteOnlineAnnotationPoolCase(pathId, caseId);
      setPoolDetailCases((prev) => prev.filter((item) => item.id !== caseId));
      setPoolPaths((prev) =>
        prev.map((item) =>
          item.id === pathId
            ? { ...item, case_count: Math.max((item.case_count || 0) - 1, 0) }
            : item
        )
      );
      setPoolDetailPath((prev) =>
        prev?.id === pathId
          ? { ...prev, case_count: Math.max((prev.case_count || 0) - 1, 0) }
          : prev
      );
      message.success("标注集 case 已删除");
    } catch (e: unknown) {
      message.error(formatApiError(e, "删除标注集 case 失败"));
      if (poolDetailPath?.id === pathId) {
        void openPoolPathDetail(poolDetailPath);
      }
      void reloadPoolPaths();
    } finally {
      setPoolDeletingCaseId(null);
    }
  };

  const deletePoolPath = async (pathId: number) => {
    setPoolDeletingPathId(pathId);
    try {
      await api.deleteOnlineAnnotationPoolPath(pathId);
      setPoolPaths((prev) => prev.filter((item) => item.id !== pathId));
      if (poolDetailPath?.id === pathId) closePoolPathDetail();
      message.success("标注集已删除");
    } catch (e: unknown) {
      message.error(formatApiError(e, "删除标注集失败"));
      void reloadPoolPaths();
    } finally {
      setPoolDeletingPathId(null);
    }
  };

  const exportPoolPath = async (pathId: number) => {
    setPoolExportingPathId(pathId);
    try {
      const res = await api.exportOnlineAnnotationPoolPath(pathId, "");
      Modal.success({
        title: "标注池清单已导出到飞书",
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
      message.error(formatApiError(e, "导出标注池清单失败"));
      return false;
    } finally {
      setPoolExportingPathId(null);
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
    poolPathForm,
    rows,
    onlineBenchmarks: ((benchmarksData ?? []) as Benchmark[]).filter((b) => b.source === "online"),
    benchmarkNameById: Object.fromEntries(
      ((benchmarksData ?? []) as Benchmark[]).map((b) => [b.id, b.name])
    ) as Record<number, string>,
    judgeModels: (judgeModelsData ?? []) as JudgeModel[],
    loading,
    poolPaths,
    poolLoading,
    poolError,
    poolSubmitting,
    poolImporting,
    poolAddingCaseId,
    poolExportingPathId,
    poolUpdatingPathId,
    poolDeletingPathId,
    poolEditingPath,
    poolDetailPath,
    poolDetailCases,
    poolDetailLoading,
    poolDeletingCaseId,
    progress,
    loadError: listError ?? benchmarksError ?? judgeModelsError,
    reload,
    submitting,
    submit,
    detail,
    detailLoading,
    deletingCaseId,
    rescoringCaseId,
    openDetail,
    deleteEval,
    deleteCase,
    rescoreCase,
    reloadPoolPaths,
    createPoolPath,
    importPoolPathFromFeishu,
    addCaseToPool,
    updatePoolPath,
    openPoolPathEdit: setPoolEditingPath,
    closePoolPathEdit: () => setPoolEditingPath(null),
    openPoolPathDetail,
    closePoolPathDetail,
    deletePoolPath,
    deletePoolCase,
    exportPoolPath,
    closeDetail: () => setDetail(null),
  };
}
