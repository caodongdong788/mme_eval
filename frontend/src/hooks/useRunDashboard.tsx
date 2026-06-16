import { useEffect, useMemo, useState } from "react";
import { Form, Modal, message } from "antd";
import { useLocation, useNavigate } from "react-router-dom";
import {
  api,
  Benchmark,
  CASE_LIST_LIMIT,
  CaseRow,
  JudgeModel,
  RejudgePayload,
  ReviewStats,
  RunDetail,
  RunDiff,
  RunSummary,
} from "../api/index";
import { useBenchmarkYamlActions } from "./useBenchmarkYamlActions";
import { useYamlEditorState } from "./useYamlEditorState";
import { CaseFilters } from "../components/FilterToolbar";
import { formatApiError } from "../utils/apiError";

function readSavedFilters(filtersKey: string): {
  filters: CaseFilters;
  onlyPending: boolean;
  reviewFilter?: string;
} {
  try {
    const raw = sessionStorage.getItem(filtersKey);
    if (raw) return JSON.parse(raw);
  } catch {
    /* ignore */
  }
  return { filters: {}, onlyPending: false };
}

export function useRunDashboard(runId: number) {
  const navigate = useNavigate();
  const location = useLocation();
  const filtersKey = `run:${runId}:caseFilters`;
  const saved = readSavedFilters(filtersKey);

  const [run, setRun] = useState<RunDetail | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [filters, setFilters] = useState<CaseFilters>(() => saved.filters);
  const [reviewStats, setReviewStats] = useState<ReviewStats | null>(null);
  const [queueIds, setQueueIds] = useState<Set<string>>(new Set());
  const [onlyPending, setOnlyPending] = useState<boolean>(() => saved.onlyPending);
  const [reviewFilter, setReviewFilter] = useState<string | undefined>(
    () => saved.reviewFilter
  );
  const [activeTab, setActiveTab] = useState<string>(
    () => ((location.state as { tab?: string } | null)?.tab) || "overview"
  );
  const [otherRuns, setOtherRuns] = useState<RunSummary[]>([]);
  const [diff, setDiff] = useState<RunDiff | null>(null);
  const [diffBaselineId, setDiffBaselineId] = useState<number | null>(null);
  const [baselineCases, setBaselineCases] = useState<CaseRow[]>([]);
  const [diffCurrentCases, setDiffCurrentCases] = useState<CaseRow[]>([]);
  const [diffLoading, setDiffLoading] = useState(false);
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

  const isBuiltinBenchmark =
    benchmarks.find((b) => b.id === run?.benchmark_id)?.source === "builtin";

  useEffect(() => {
    sessionStorage.setItem(
      filtersKey,
      JSON.stringify({ filters, onlyPending, reviewFilter })
    );
  }, [filtersKey, filters, onlyPending, reviewFilter]);

  useEffect(() => {
    setRunError(null);
    api
      .getRun(runId)
      .then((r) => {
        setRun(r);
        if (r.benchmark_id != null) {
          api
            .listBenchmarks()
            .then((bs) => setBenchmarkName(bs.find((b) => b.id === r.benchmark_id)?.name))
            .catch(() => undefined);
        }
      })
      .catch((e) => setRunError(formatApiError(e, "加载评测详情失败")));
    api
      .listRuns()
      .then((rs) =>
        setOtherRuns(rs.filter((r) => r.id !== runId && r.status === "success"))
      );
  }, [runId]);

  useEffect(() => {
    const params: Record<string, string | number | boolean> = {
      ...filters,
      limit: CASE_LIST_LIMIT,
    };
    if (onlyPending) params.review_pending = true;
    api.listCaseResults(runId, params).then(setCases);
    api.getReviewStats(runId).then(setReviewStats).catch(() => setReviewStats(null));
    api
      .getReviewQueue(runId, filters)
      .then((q) => setQueueIds(new Set(q.map((it) => it.sample_id))))
      .catch(() => setQueueIds(new Set()));
  }, [runId, filters, onlyPending]);

  const shownCases = useMemo(() => {
    let result = cases;
    if (reviewFilter === "agree" || reviewFilter === "override") {
      result = result.filter((c) => c.review?.verdict === reviewFilter);
    } else if (reviewFilter === "none") {
      result = result.filter((c) => !c.review);
    }
    return result;
  }, [cases, reviewFilter]);

  const hasActiveFilters =
    onlyPending ||
    reviewFilter != null ||
    ["release_passed", "level", "turns", "stability", "guideline"].some(
      (k) => filters[k] != null
    );

  const resetFilters = () => {
    setFilters({});
    setReviewFilter(undefined);
    setOnlyPending(false);
  };

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
      const created = await api.resumeRun(runId);
      message.success(`续跑已发起（新评测 #${created.id}），跳转中…`);
      navigate(`/runs/${created.id}`);
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
    openFromRun(runId, filters);
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
        ...filters,
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

  const selectDiffBaseline = async (againstId: number) => {
    setDiffBaselineId(againstId);
    setDiffLoading(true);
    setActiveTab("diff");
    try {
      const [diffResult, baseCases, curCases] = await Promise.all([
        api.diffRun(runId, againstId),
        api.listCaseResults(againstId, { limit: CASE_LIST_LIMIT }),
        api.listCaseResults(runId, { limit: CASE_LIST_LIMIT }),
      ]);
      setDiff(diffResult);
      setBaselineCases(baseCases);
      setDiffCurrentCases(curCases);
    } catch (e: unknown) {
      setDiff(null);
      setBaselineCases([]);
      setDiffCurrentCases([]);
      message.error(formatApiError(e, "加载对比数据失败"));
    } finally {
      setDiffLoading(false);
    }
  };

  return {
    run,
    runError,
    cases,
    shownCases,
    filters,
    setFilters,
    reviewStats,
    queueIds,
    onlyPending,
    setOnlyPending,
    reviewFilter,
    setReviewFilter,
    activeTab,
    setActiveTab,
    otherRuns,
    diff,
    diffBaselineId,
    baselineCases,
    diffCurrentCases,
    diffLoading,
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
    hasActiveFilters,
    resetFilters,
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
    selectDiffBaseline,
    navigate,
  };
}
