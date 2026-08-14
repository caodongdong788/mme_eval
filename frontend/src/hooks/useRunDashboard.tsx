import { useEffect, useState } from "react";
import { Form, Modal, message } from "antd";
import { useLocation, useNavigate } from "react-router-dom";
import {
  api,
  Benchmark,
  CaseRow,
  JudgeModel,
  ProgressInfo,
  RejudgePayload,
  RunDetail,
} from "../api/index";
import { useBenchmarkYamlActions } from "./useBenchmarkYamlActions";
import { useRunCaseFilters } from "./useRunCaseFilters";
import { useRunDiff } from "./useRunDiff";
import { useYamlEditorState } from "./useYamlEditorState";
import { formatApiError } from "../utils/apiError";

export function useRunDashboard(runId: number, failureTagLabel: (tag: string) => string) {
  const navigate = useNavigate();
  const location = useLocation();
  const routeState = location.state as { tab?: string; attributionTaskId?: number } | null;

  const [run, setRun] = useState<RunDetail | null>(null);
  const [progress, setProgress] = useState<ProgressInfo | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>(
    () => routeState?.tab || "overview"
  );
  const [exporting, setExporting] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [acting, setActing] = useState(false);
  const [rejudgeOpen, setRejudgeOpen] = useState(false);
  const [rejudgeForm] = Form.useForm();
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [benchmarkName, setBenchmarkName] = useState<string | undefined>();
  const [judgeModels, setJudgeModels] = useState<JudgeModel[]>([]);
  const {
    yamlOpen,
    setYamlOpen,
    yamlText,
    setYamlText,
    yamlName,
    setYamlName,
    yamlLoading,
    openFromRun,
  } = useYamlEditorState(run?.name);
  const yamlActions = useBenchmarkYamlActions({
    benchmarkId: run?.benchmark_id,
    getYamlText: () => yamlText,
  });
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [attributionLaunchOpen, setAttributionLaunchOpen] = useState(false);
  const [attributionCases, setAttributionCases] = useState<CaseRow[]>([]);
  const [attributionLaunching, setAttributionLaunching] = useState(false);
  const [attributionTaskId, setAttributionTaskId] = useState<number | undefined>(
    () => routeState?.attributionTaskId,
  );

  const caseFilters = useRunCaseFilters(
    runId,
    failureTagLabel,
    activeTab === "detail" || activeTab === "attribution",
    run?.status,
  );
  const runDiff = useRunDiff(runId, () => setActiveTab("diff"), activeTab === "diff");

  const isBuiltinBenchmark =
    benchmarks.find((b) => b.id === run?.benchmark_id)?.source === "builtin";

  useEffect(() => {
    setRunError(null);
    setProgress(null);
    api
      .getRun(runId)
      .then((r) => {
        setRun(r);
        // 重新评测完成后，后端会保留本次操作的用例级进度。首次进入页面也要
        // 拉取它，不能只在运行中轮询，否则刷新页面会丢掉完成态进度条。
        void api.getProgress(runId).then(setProgress).catch(() => undefined);
        if (r.benchmark_id != null) {
          api
            .listBenchmarks()
            .then((bs) => setBenchmarkName(bs.find((b) => b.id === r.benchmark_id)?.name))
            .catch(() => undefined);
        }
      })
      .catch((e) => setRunError(formatApiError(e, "加载评测详情失败")));
  }, [runId]);

  useEffect(() => {
    if (run?.status !== "running" && run?.status !== "pending") return;
    let alive = true;
    const refresh = () => {
      if (document.visibilityState !== "visible") return;
      void Promise.all([api.getRun(runId), api.getProgress(runId)])
        .then(([nextRun, nextProgress]) => {
          if (!alive) return;
          setRun(nextRun);
          setProgress(nextProgress);
        })
        .catch(() => undefined);
    };
    refresh();
    const timer = window.setInterval(refresh, 2000);
    const onVisibility = () => refresh();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      alive = false;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [runId, run?.status]);

  const startEditName = () => {
    if (!run) return;
    setNameDraft(run.name || run.run_slug || "");
    setEditingName(true);
  };

  const commitName = async () => {
    if (!run) return;
    const next = nameDraft.trim();
    setEditingName(false);
    if (!next || next === run.name) return;
    setSavingName(true);
    try {
      const updated = await api.renameRun(runId, next);
      setRun({ ...run, name: updated.name });
      message.success("评测名称已更新");
    } catch (e: unknown) {
      message.error(formatApiError(e, "改名失败"));
    } finally {
      setSavingName(false);
    }
  };

  const doResume = async () => {
    setActing(true);
    try {
      await api.resumeRun(runId);
      setRun(await api.getRun(runId));
      message.success("已在当前评测记录中继续运行");
    } catch (e: unknown) {
      message.error(formatApiError(e, "操作失败"));
    } finally {
      setActing(false);
    }
  };

  const openRejudge = () => {
    rejudgeForm.setFieldsValue({
      cases_benchmark_id: undefined,
      judge_model_id: undefined,
      only_release_failed: false,
    });
    if (benchmarks.length === 0) api.listBenchmarks().then(setBenchmarks);
    if (judgeModels.length === 0) api.listJudgeModels().then(setJudgeModels);
    setRejudgeOpen(true);
  };

  const submitRejudge = async () => {
    const v = await rejudgeForm.validateFields();
    const payload: RejudgePayload = {};
    if (v.cases_benchmark_id != null) payload.cases_benchmark_id = v.cases_benchmark_id;
    if (v.judge_model_id != null) payload.judge_model_id = v.judge_model_id;
    if (v.only_release_failed) payload.only_release_failed = true;

    setActing(true);
    try {
      const created = await api.rejudgeRun(runId, payload);
      setRejudgeOpen(false);
      message.success(`重判已发起（新评测 #${created.id}），跳转中…`);
      navigate(`/runs/${created.id}`);
    } catch (e: unknown) {
      message.error(formatApiError(e, "操作失败"));
    } finally {
      setActing(false);
    }
  };

  const togglePin = async () => {
    if (!run) return;
    setActing(true);
    try {
      const res = await api.setPin(runId, !run.pinned);
      setRun({ ...run, pinned: res.pinned });
      message.success(res.pinned ? "已置顶保护（免清理）" : "已取消置顶");
    } catch (e: unknown) {
      message.error(formatApiError(e, "操作失败"));
    } finally {
      setActing(false);
    }
  };

  const openYamlEditor = () => {
    if (benchmarks.length === 0) api.listBenchmarks().then(setBenchmarks);
    openFromRun(runId, {});
  };

  const saveYamlAsBenchmark = () =>
    yamlActions.saveAsBenchmark({
      name: yamlName,
      description: `从 #${run?.benchmark_id} 改判据派生`,
      onSuccess: (bm) => {
        setBenchmarks([]);
        setYamlOpen(false);
        Modal.success({
          title: "已另存为新 benchmark",
          content: `新 benchmark #${bm.id}「${bm.name}」已创建。可在右上「重判」里选它发起重判。`,
        });
      },
    });

  const saveYamlOverwrite = () =>
    yamlActions.overwriteBenchmark({
      confirmContent:
        "将用编辑后的判据就地覆盖原 benchmark（合并语义同另存：按 sample_id 只合并判据字段、未匹配丢弃、未编辑用例保留）。此操作不可撤销，且不影响任何历史评测的冻结结果。",
      onSuccess: (bm) => {
        setBenchmarks([]);
        setYamlOpen(false);
        Modal.success({
          title: "已覆盖保存",
          content: `benchmark #${bm.id}「${bm.name}」判据已更新。`,
        });
      },
    });

  const doExport = async () => {
    setExporting(true);
    try {
      const res = await api.exportTranscripts(runId, {
        parent_folder_token: "",
      });
      setExportOpen(false);
      Modal.success({
        title: "对话流水已导出到飞书",
        content: (
          <span>
            共 {res.count} 条用例，文件名 {res.filename}：
            <br />
            <a href={res.url} target="_blank" rel="noreferrer">
              点击打开飞书表格
            </a>
          </span>
        ),
      });
    } catch (e: unknown) {
      message.error(formatApiError(e, "导出失败"));
    } finally {
      setExporting(false);
    }
  };

  const openAttributionLaunch = (rows: CaseRow[]) => {
    setAttributionCases(rows);
    if (judgeModels.length === 0) api.listJudgeModels().then(setJudgeModels).catch(() => undefined);
    setAttributionLaunchOpen(true);
  };

  const startAttributionTask = async (judgeModelId: number) => {
    const sampleIds = attributionCases.map((item) => item.sample_id);
    if (!sampleIds.length) return;
    setAttributionLaunching(true);
    try {
      const task = await api.createAttributionTask(runId, {
        sample_ids: sampleIds,
        judge_model_id: judgeModelId,
      });
      setAttributionLaunchOpen(false);
      setAttributionTaskId(task.id);
      setActiveTab("attribution");
      message.success(`归因任务已创建，将并发分析 ${task.total_count} 条不合格用例`);
    } catch (e: unknown) {
      // 请求超时、旧版本启动异常或重复点击时，任务可能已经成功落库。
      // 优先带用户进入已有任务，避免出现“提示正在进行却看不到任务”的死角。
      try {
        const tasks = await api.listAttributionTasks(runId);
        const activeTask = tasks.find((item) => item.status === "queued" || item.status === "running");
        if (activeTask) {
          setAttributionLaunchOpen(false);
          setAttributionTaskId(activeTask.id);
          setActiveTab("attribution");
          message.warning(`已打开进行中的归因任务 #${activeTask.id}`);
          return;
        }
      } catch {
        // 保留原始创建错误，便于用户判断真正的失败原因。
      }
      message.error(formatApiError(e, "创建归因任务失败"));
    } finally {
      setAttributionLaunching(false);
    }
  };

  const retrySelectedCases = async (rows: CaseRow[]) => {
    if (!rows.length) return;
    const count = rows.length;
    Modal.confirm({
      title: `重新评测 ${count} 条用例？`,
      content: "将重新调用 AI 助手并执行完整判分，完成后会原位覆盖这些用例的结果。",
      okText: "开始重新评测",
      cancelText: "取消",
      onOk: async () => {
        setActing(true);
        try {
          await api.retryCases(runId, rows.map((row) => row.sample_id));
          const [nextRun, nextProgress] = await Promise.all([
            api.getRun(runId),
            api.getProgress(runId),
          ]);
          setRun(nextRun);
          setProgress(nextProgress);
          message.success(`已开始重新评测 ${count} 条用例`);
        } catch (e: unknown) {
          message.error(formatApiError(e, "重新评测失败"));
        } finally {
          setActing(false);
        }
      },
    });
  };

  const cancelRetrySelectedCases = async () => {
    setActing(true);
    try {
      await api.cancelRetryCases(runId);
      const [nextRun, nextProgress] = await Promise.all([
        api.getRun(runId),
        api.getProgress(runId),
      ]);
      setRun(nextRun);
      setProgress(nextProgress);
      message.success("已终止重新评测，未完成的用例已标记为已取消");
    } catch (e: unknown) {
      message.error(formatApiError(e, "终止重新评测失败"));
    } finally {
      setActing(false);
    }
  };

  return {
    run,
    progress,
    runError,
    ...caseFilters,
    activeTab,
    setActiveTab,
    ...runDiff,
    exporting,
    exportOpen,
    setExportOpen,
    acting,
    rejudgeOpen,
    setRejudgeOpen,
    rejudgeForm,
    benchmarks,
    benchmarkName,
    judgeModels,
    yamlOpen,
    setYamlOpen,
    yamlText,
    setYamlText,
    yamlName,
    setYamlName,
    yamlLoading,
    yamlActions,
    isBuiltinBenchmark,
    editingName,
    nameDraft,
    setNameDraft,
    savingName,
    startEditName,
    commitName,
    doResume,
    openRejudge,
    submitRejudge,
    togglePin,
    openYamlEditor,
    saveYamlAsBenchmark,
    saveYamlOverwrite,
    doExport,
    attributionLaunchOpen,
    setAttributionLaunchOpen,
    attributionCases,
    attributionLaunching,
    attributionTaskId,
    setAttributionTaskId,
    openAttributionLaunch,
    startAttributionTask,
    retrySelectedCases,
    cancelRetrySelectedCases,
    navigate,
  };
}
