import { useEffect, useState } from "react";
import { Modal, message } from "antd";
import {
  Annotation,
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
    openEditor,
    runPreview,
    yamlActions,
    saveYamlAsBenchmark,
    saveYamlOverwrite,
  };
}
