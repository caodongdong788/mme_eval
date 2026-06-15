import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Form,
  Modal,
  Result,
  Space,
  Tabs,
  message,
} from "antd";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import {
  api,
  Benchmark,
  CaseRow,
  JudgeModel,
  RejudgePayload,
  ReviewStats,
  RunDetail,
  RunDiff,
  RunSummary,
} from "../api";
import { useFailureTagLabels } from "../failureTags";
import { formatApiError } from "../utils/apiError";
import { useBenchmarkYamlActions } from "../hooks/useBenchmarkYamlActions";
import { ExportTranscriptsModal } from "../components/ExportTranscriptsModal";
import { RejudgeModal } from "../components/RejudgeModal";
import { EditCriteriaDrawer } from "../components/EditCriteriaDrawer";
import { RunOverviewTab } from "../components/RunOverviewTab";
import { buildCaseColumns } from "../components/caseColumns";
import { CaseFilters } from "../components/FilterToolbar";
import { RunDashboardHeader } from "../components/RunDashboardHeader";
import { RunCaseResultsCard } from "../components/RunCaseResultsCard";
import { RunDiffCard } from "../components/RunDiffCard";

export default function RunDashboardPage() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const id = Number(runId);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [cases, setCases] = useState<CaseRow[]>([]);
  const filtersKey = `run:${id}:caseFilters`;
  const readSavedFilters = (): {
    filters: CaseFilters;
    onlyPending: boolean;
    reviewFilter?: string;
  } => {
    try {
      const raw = sessionStorage.getItem(filtersKey);
      if (raw) return JSON.parse(raw);
    } catch {
      /* ignore */
    }
    return { filters: {}, onlyPending: false };
  };
  const [filters, setFilters] = useState<CaseFilters>(() => readSavedFilters().filters);
  const [reviewStats, setReviewStats] = useState<ReviewStats | null>(null);
  const [queueIds, setQueueIds] = useState<Set<string>>(new Set());
  const [onlyPending, setOnlyPending] = useState<boolean>(() => readSavedFilters().onlyPending);
  const [reviewFilter, setReviewFilter] = useState<string | undefined>(
    () => readSavedFilters().reviewFilter
  );
  const location = useLocation();
  const [activeTab, setActiveTab] = useState<string>(
    () => ((location.state as { tab?: string } | null)?.tab) || "overview"
  );
  const tagLabel = useFailureTagLabels();

  useEffect(() => {
    sessionStorage.setItem(
      filtersKey,
      JSON.stringify({ filters, onlyPending, reviewFilter })
    );
  }, [filtersKey, filters, onlyPending, reviewFilter]);
  const [otherRuns, setOtherRuns] = useState<RunSummary[]>([]);
  const [diff, setDiff] = useState<RunDiff | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [acting, setActing] = useState(false);
  const [rejudgeOpen, setRejudgeOpen] = useState(false);
  const [rejudgeForm] = Form.useForm();
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [benchmarkName, setBenchmarkName] = useState<string | undefined>();
  const [judgeModels, setJudgeModels] = useState<JudgeModel[]>([]);
  const [yamlOpen, setYamlOpen] = useState(false);
  const [yamlText, setYamlText] = useState("");
  const [yamlName, setYamlName] = useState("");
  const [yamlLoading, setYamlLoading] = useState(false);
  const yamlActions = useBenchmarkYamlActions({
    benchmarkId: run?.benchmark_id,
    getYamlText: () => yamlText,
  });

  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [savingName, setSavingName] = useState(false);

  const isBuiltinBenchmark =
    benchmarks.find((b) => b.id === run?.benchmark_id)?.source === "builtin";

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
      const updated = await api.renameRun(id, next);
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
      const created = await api.resumeRun(id);
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
      const created = await api.rejudgeRun(id, payload);
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
      const res = await api.setPin(id, !run.pinned);
      setRun({ ...run, pinned: res.pinned });
      message.success(res.pinned ? "已置顶保护（免清理）" : "已取消置顶");
    } catch (e: unknown) {
      message.error(formatApiError(e, "操作失败"));
    } finally {
      setActing(false);
    }
  };

  const openYamlEditor = async () => {
    setYamlOpen(true);
    setYamlLoading(true);
    setYamlText("");
    if (benchmarks.length === 0) api.listBenchmarks().then(setBenchmarks);
    try {
      const res = await api.getRunCasesYaml(id, filters);
      setYamlText(res.yaml_text);
      setYamlName(
        `${run?.name || "派生"} · 改判据 ${new Date()
          .toISOString()
          .slice(5, 16)
          .replace("T", "-")}`
      );
    } catch (e: unknown) {
      message.error(formatApiError(e, "加载用例 YAML 失败"));
      setYamlOpen(false);
    } finally {
      setYamlLoading(false);
    }
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
      const res = await api.exportTranscripts(id, {
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

  useEffect(() => {
    setRunError(null);
    api
      .getRun(id)
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
    api.listRuns().then((rs) => setOtherRuns(rs.filter((r) => r.id !== id && r.status === "success")));
  }, [id]);

  useEffect(() => {
    api.listCaseResults(id, filters).then(setCases);
    api.getReviewStats(id).then(setReviewStats).catch(() => setReviewStats(null));
    api
      .getReviewQueue(id, filters)
      .then((q) => setQueueIds(new Set(q.map((it) => it.sample_id))))
      .catch(() => setQueueIds(new Set()));
  }, [id, filters]);

  let shownCases = cases;
  if (onlyPending) {
    shownCases = shownCases.filter((c) => queueIds.has(c.sample_id) && !c.review);
  }
  if (reviewFilter === "agree" || reviewFilter === "override") {
    shownCases = shownCases.filter((c) => c.review?.verdict === reviewFilter);
  } else if (reviewFilter === "none") {
    shownCases = shownCases.filter((c) => !c.review);
  }

  if (runError)
    return (
      <Result
        status="warning"
        title="无法加载评测详情"
        subTitle={runError}
        extra={
          <Button type="primary" onClick={() => navigate("/runs")}>
            返回评测列表
          </Button>
        }
      />
    );
  if (!run) return <Card loading />;

  const columns = buildCaseColumns(id, tagLabel);

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

  return (
    <Space direction="vertical" size={16} style={{ display: "flex" }}>
      <RunDashboardHeader
        run={run}
        editingName={editingName}
        nameDraft={nameDraft}
        savingName={savingName}
        acting={acting}
        onNameDraftChange={setNameDraft}
        onStartEditName={startEditName}
        onCommitName={commitName}
        onRejudge={openRejudge}
        onResume={doResume}
        onTogglePin={togglePin}
      />

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: "overview",
            label: "概览",
            children: <RunOverviewTab run={run} reviewStats={reviewStats} />,
          },
          {
            key: "detail",
            label: "用例明细",
            children: (
              <RunCaseResultsCard
                benchmarkName={benchmarkName}
                reviewStats={reviewStats}
                cases={cases}
                shownCases={shownCases}
                columns={columns}
                filters={filters}
                setFilters={setFilters}
                reviewFilter={reviewFilter}
                setReviewFilter={setReviewFilter}
                onlyPending={onlyPending}
                setOnlyPending={setOnlyPending}
                queueIds={queueIds}
                hasActiveFilters={hasActiveFilters}
                resetFilters={resetFilters}
                exporting={exporting}
                onOpenYamlEditor={openYamlEditor}
                onOpenExport={() => setExportOpen(true)}
              />
            ),
          },
        ]}
      />

      <ExportTranscriptsModal
        open={exportOpen}
        caseCount={cases.length}
        loading={exporting}
        onOk={doExport}
        onCancel={() => setExportOpen(false)}
      />

      <RejudgeModal
        open={rejudgeOpen}
        loading={acting}
        form={rejudgeForm}
        benchmarks={benchmarks}
        judgeModels={judgeModels}
        onOk={submitRejudge}
        onCancel={() => setRejudgeOpen(false)}
      />

      <EditCriteriaDrawer
        open={yamlOpen}
        loading={yamlActions.saving}
        isBuiltin={isBuiltinBenchmark}
        benchmarkLabel={
          run?.benchmark_id
            ? `#${run.benchmark_id}「${
                benchmarks.find((b) => b.id === run.benchmark_id)?.name ||
                benchmarkName ||
                "—"
              }」`
            : undefined
        }
        name={yamlName}
        onNameChange={setYamlName}
        yamlText={yamlText}
        onYamlChange={setYamlText}
        yamlLoading={yamlLoading}
        onClose={() => setYamlOpen(false)}
        onSaveAs={saveYamlAsBenchmark}
        onOverwrite={saveYamlOverwrite}
      />

      <RunDiffCard
        otherRuns={otherRuns}
        diff={diff}
        onSelectBaseline={async (v) => setDiff(await api.diffRun(id, v))}
      />
    </Space>
  );
}
