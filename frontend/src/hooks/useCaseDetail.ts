import { useEffect, useRef, useState } from "react";
import { Modal, message } from "antd";
import {
  Annotation,
  CASE_LIST_LIMIT,
  PreviewRejudgeResult,
  RunDetail,
  api,
} from "../api/index";
import { formatApiError } from "../utils/apiError";
import { useBenchmarkYamlActions } from "./useBenchmarkYamlActions";
import { useYamlEditorState } from "./useYamlEditorState";

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
  const [chainSyncing, setChainSyncing] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [nextSampleId, setNextSampleId] = useState<string | undefined>();
  // 每次进入一个 Case 最多自动补同步一次；避免 Langfuse 仍在 ingest 时反复请求。
  const autoChainSyncKeyRef = useRef<string | null>(null);

  const {
    yamlOpen,
    setYamlOpen,
    yamlLoading,
    yamlText,
    setYamlText,
    yamlName,
    setYamlName,
    openFromRun,
  } = useYamlEditorState(run?.name);

  const yamlActions = useBenchmarkYamlActions({
    benchmarkId: run?.benchmark_id,
    getYamlText: () => yamlText,
  });

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
      .listCaseResults(runId, { limit: CASE_LIST_LIMIT })
      .then((cases) => {
        if (!alive) return;
        const index = cases.findIndex((item) => item.sample_id === sampleId);
        setNextSampleId(index >= 0 ? cases[index + 1]?.sample_id : undefined);
      })
      .catch(() => alive && setNextSampleId(undefined));
    return () => {
      alive = false;
    };
  }, [runId, sampleId]);

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

  const openEditor = () => {
    if (!sampleId) return;
    openFromRun(runId, { sample_id: sampleId }, { onBeforeOpen: () => setPreviewResult(null) });
  };

  const runPreview = async () => {
    if (!sampleId) return;
    setPreviewing(true);
    try {
      const res = await api.previewRejudgeCase(runId, sampleId, { yaml_text: yamlText });
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
    try {
      await api.retryCase(runId, sampleId);
      message.info("已开始重试该 Case，完成后会自动刷新结果");
    } catch (e: unknown) {
      setRetrying(false);
      message.error(formatApiError(e, "提交重试失败"));
    }
  };

  useEffect(() => {
    if (!retrying || !sampleId) return undefined;
    const timer = window.setInterval(() => {
      api.getRun(runId).then(async (next) => {
        setRun(next);
        if (next.status === "pending" || next.status === "running") return;
        window.clearInterval(timer);
        setRetrying(false);
        if (next.status === "success") {
          try {
            const refreshed = await api.getCaseDetail(runId, sampleId);
            setDetail(refreshed);
            message.success("Case 重试完成，已更新结果");
          } catch (e: unknown) {
            message.error(formatApiError(e, "重试完成，但刷新结果失败"));
          }
        } else {
          message.error(next.error_msg || "Case 重试失败");
        }
      }).catch(() => {});
    }, 1500);
    return () => window.clearInterval(timer);
  }, [retrying, runId, sampleId]);

  const saveYamlAsBenchmark = () =>
    yamlActions.saveAsBenchmark({
      name: yamlName,
      description: `从 #${run?.benchmark_id} 改判据派生（用例 ${sampleId}）`,
      onSuccess: (bm) => {
        setYamlOpen(false);
        Modal.success({
          title: "已另存为新 benchmark",
          content: `新 benchmark #${bm.id}「${bm.name}」已创建。可在看板「重判」里选它发起重判。`,
        });
      },
    });

  const saveYamlOverwrite = () =>
    yamlActions.overwriteBenchmark({
      confirmContent:
        "将用编辑后的判据就地覆盖这次评测当前关联的 benchmark（按 sample_id 只合并判据字段）。" +
        "此操作仅更新判据源、不改当前 run 已存分；要让某个 run 反映新判据需另行「重判」。不可撤销。",
      onSuccess: (bm) => {
        setYamlOpen(false);
        Modal.success({
          title: "已覆盖当前 benchmark",
          content: `benchmark #${bm.id}「${bm.name}」判据已更新。要让评测反映新判据，请到看板「重判」。`,
        });
      },
    });

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
    yamlOpen,
    setYamlOpen,
    yamlLoading,
    yamlText,
    setYamlText,
    yamlName,
    setYamlName,
    previewing,
    previewResult,
    chainSyncing,
    syncAgentChain,
    retrying,
    retryCase,
    nextSampleId,
    openEditor,
    runPreview,
    yamlActions,
    saveYamlAsBenchmark,
    saveYamlOverwrite,
  };
}
