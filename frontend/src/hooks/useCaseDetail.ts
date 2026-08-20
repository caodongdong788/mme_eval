import { useEffect, useRef, useState } from "react";
import { Modal, message } from "antd";
import {
  Annotation,
  BenchmarkCaseContent,
  PreviewRejudgeResult,
  ProgressInfo,
  RunDetail,
  api,
} from "../api/index";
import { formatApiError, humanizeErrorText } from "../utils/apiError";
import { isActiveCaseRetry } from "../utils/caseRetryProgress";
import { usePollingTask } from "./usePollingTask";

export function useCaseDetail(runId: number, sampleId: string | undefined) {
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [verdict, setVerdict] = useState<"agree" | "override">("agree");
  const [suggestion, setSuggestion] = useState("");
  const [comment, setComment] = useState("");
  const [saving, setSaving] = useState(false);

  const [run, setRun] = useState<RunDetail | null>(null);
  const [benchmarkName, setBenchmarkName] = useState<string | undefined>();
  const [isBuiltin, setIsBuiltin] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [previewResult, setPreviewResult] = useState<PreviewRejudgeResult | null>(null);
  const [criteriaOpen, setCriteriaOpen] = useState(false);
  const [criteriaLoading, setCriteriaLoading] = useState(false);
  const [criteriaSaving, setCriteriaSaving] = useState(false);
  const [caseContent, setCaseContent] = useState<BenchmarkCaseContent | null>(null);
  const [chainSyncing, setChainSyncing] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [retryPolling, setRetryPolling] = useState(false);
  const [retryProgress, setRetryProgress] = useState<ProgressInfo | null>(null);
  const [nextSampleId, setNextSampleId] = useState<string | undefined>();
  // 每次进入一个 Case 最多自动补同步一次；避免 Langfuse 仍在 ingest 时反复请求。
  const autoChainSyncKeyRef = useRef<string | null>(null);

  const loadAnnotations = () => {
    if (sampleId) api.getCaseAnnotations(runId, sampleId).then(setAnnotations);
  };

  useEffect(() => {
    if (sampleId) {
      setDetailError(null);
      api
        .getCaseDetail(runId, sampleId)
        .then(setDetail)
        .catch((e) => setDetailError(formatApiError(e, "加载用例明细失败")));
    }
    loadAnnotations();
    Promise.all([api.getRun(runId), api.listBenchmarks()])
      .then(([r, list]) => {
        setRun(r);
        const bm = list.find((b) => b.id === r.benchmark_id);
        setBenchmarkName(bm?.name);
        setIsBuiltin(bm?.source === "builtin");
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, sampleId]);

  useEffect(() => {
    if (!sampleId) return undefined;
    let alive = true;
    setRetrying(false);
    setRetryPolling(false);
    setRetryProgress(null);
    api
      .getProgress(runId)
      .then((next) => {
        if (!alive || !isActiveCaseRetry(next, sampleId)) return;
        setRetryProgress(next);
        setRetrying(true);
        setRetryPolling(true);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [runId, sampleId]);

  useEffect(() => {
    if (!sampleId || !detail) return;
    const trace = detail.trace as Record<string, unknown> | undefined;
    const chain = trace?.agent_chain as Record<string, unknown> | undefined;
    const traceIds = Array.isArray(chain?.trace_ids)
      ? chain.trace_ids
      : Array.isArray(trace?.langfuse_trace_ids)
        ? trace.langfuse_trace_ids
        : [];
    const status = typeof chain?.status === "string" ? chain.status : "";
    const canRetry = traceIds.length > 0 && status !== "synced" && status !== "unconfigured";
    const syncKey = `${runId}:${sampleId}`;
    if (!canRetry || autoChainSyncKeyRef.current === syncKey) return;

    autoChainSyncKeyRef.current = syncKey;
    let alive = true;
    setChainSyncing(true);
    api
      .syncCaseAgentChain(runId, sampleId)
      .then((next) => alive && setDetail(next))
      // 自动补同步失败时保留当前状态；用户仍可点击“重新同步”查看或手动重试。
      .catch(() => undefined)
      .finally(() => alive && setChainSyncing(false));
    return () => {
      alive = false;
    };
  }, [detail, runId, sampleId]);

  useEffect(() => {
    let alive = true;
    setNextSampleId(undefined);
    api
      .getNextCase(runId, sampleId || "")
      .then((next) => alive && setNextSampleId(next.sample_id || undefined))
      .catch(() => alive && setNextSampleId(undefined));
    return () => {
      alive = false;
    };
  }, [runId, sampleId]);

  const loadRagAudit = async () => {
    if (!sampleId) return [];
    const result = await api.getCaseRagAudit(runId, sampleId);
    return result.calls as import("../components/AgentChainPanel").RagAuditCall[];
  };

  const submitAnnotation = async () => {
    if (!sampleId) return;
    setSaving(true);
    try {
      await api.annotateCase(runId, sampleId, {
        verdict,
        suggestion: suggestion.trim() || undefined,
        comment: comment.trim() || undefined,
      });
      message.success("裁定已记录（不影响机器判分）");
      setSuggestion("");
      setComment("");
      loadAnnotations();
    } catch (e: unknown) {
      message.error(formatApiError(e, "提交失败"));
    } finally {
      setSaving(false);
    }
  };

  const openEditor = async () => {
    if (!sampleId || !run?.benchmark_id) {
      message.error("该评测未关联 benchmark，无法修改判据");
      return;
    }
    setCriteriaOpen(true);
    setCriteriaLoading(true);
    setPreviewResult(null);
    setCaseContent(null);
    try {
      setCaseContent(await api.getBenchmarkCaseContent(run.benchmark_id, sampleId));
    } catch (e: unknown) {
      message.error(formatApiError(e, "加载 benchmark 用例失败"));
      setCriteriaOpen(false);
    } finally {
      setCriteriaLoading(false);
    }
  };

  const runPreview = async () => {
    if (!sampleId || !caseContent) return;
    setPreviewing(true);
    try {
      const res = await api.previewRejudgeCase(runId, sampleId, {
        case_override: {
          sample_id: sampleId,
          evaluation: (caseContent.case.evaluation || {}) as Record<string, unknown>,
        },
      });
      setPreviewResult(res);
    } catch (e: unknown) {
      message.error(formatApiError(e, "试判失败"));
    } finally {
      setPreviewing(false);
    }
  };

  const syncAgentChain = async () => {
    if (!sampleId) return;
    setChainSyncing(true);
    try {
      const next = await api.syncCaseAgentChain(runId, sampleId);
      setDetail(next);
      message.success("Agent 链路已同步");
    } catch (e: unknown) {
      message.error(formatApiError(e, "Agent 链路同步失败"));
    } finally {
      setChainSyncing(false);
    }
  };

  const retryCase = async () => {
    if (!sampleId || retrying) return;
    setRetrying(true);
    setRetryPolling(false);
    setRetryProgress({
      status: "pending",
      progress: { current_label: "等待开始重试", done: 0, total: 0, percent: 0 },
    });
    try {
      await api.retryCase(runId, sampleId);
      setRetryPolling(true);
      message.info("已开始重试该 Case，完成后会自动刷新页面结果");
    } catch (e: unknown) {
      setRetrying(false);
      setRetryPolling(false);
      setRetryProgress(null);
      message.error(formatApiError(e, "提交重试失败"));
    }
  };

  usePollingTask(
    async (isCurrent) => {
      if (!sampleId) return;
      const next = await api.getProgress(runId);
      if (!isCurrent()) return;
      setRetryProgress(next);
      if (next.status === "pending" || next.status === "running") return;

      if (next.status !== "success") {
        try {
          const nextRun = await api.getRun(runId);
          if (!isCurrent()) return;
          setRun(nextRun);
          message.error(
            humanizeErrorText(nextRun.error_msg, "用例重新评测失败，请稍后重试")
          );
        } catch {
          if (isCurrent()) message.error("Case 重试失败");
        }
      } else {
        try {
          const [refreshed, nextRun] = await Promise.all([
            api.getCaseDetail(runId, sampleId),
            api.getRun(runId),
          ]);
          if (!isCurrent()) return;
          // 新一次执行可能产生新的 Langfuse 链路，允许自动补同步重新执行。
          autoChainSyncKeyRef.current = null;
          setDetail(refreshed);
          setRun(nextRun);
          message.success("Case 重试完成，页面结果已更新");
        } catch (error) {
          if (isCurrent())
            message.error(formatApiError(error, "重试完成，但刷新结果失败"));
        }
      }
      if (!isCurrent()) return;
      setRetrying(false);
      setRetryPolling(false);
      setRetryProgress(null);
    },
    [runId, sampleId],
    { enabled: retryPolling && Boolean(sampleId), intervalMs: 1200 }
  );

  const saveCaseOverwrite = async () => {
    if (!sampleId || !run?.benchmark_id || !caseContent) return;
    setCriteriaSaving(true);
    try {
      const saved = await api.saveBenchmarkCaseContent(
        run.benchmark_id,
        sampleId,
        caseContent.case
      );
      setCaseContent(saved);
      setCriteriaOpen(false);
      Modal.success({
        title: "已覆盖当前 benchmark",
        content: `benchmark #${run.benchmark_id}「${benchmarkName || "—"}」中的用例 ${sampleId} 已更新。要让评测反映新判据，请到看板「重判」。`,
      });
    } catch (e: unknown) {
      message.error(formatApiError(e, "覆盖 benchmark 失败"));
    } finally {
      setCriteriaSaving(false);
    }
  };

  return {
    detail,
    detailError,
    annotations,
    verdict,
    setVerdict,
    suggestion,
    setSuggestion,
    comment,
    setComment,
    saving,
    submitAnnotation,
    run,
    benchmarkName,
    isBuiltin,
    criteriaOpen,
    setCriteriaOpen,
    criteriaLoading,
    criteriaSaving,
    caseContent,
    setCaseContent,
    previewing,
    previewResult,
    chainSyncing,
    syncAgentChain,
    retrying,
    retryProgress,
    retryCase,
    loadRagAudit,
    nextSampleId,
    openEditor,
    runPreview,
    saveCaseOverwrite,
  };
}
