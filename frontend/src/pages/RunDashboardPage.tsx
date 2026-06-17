import { Button, Result, Spin, Tabs } from "antd";
import { useParams } from "react-router-dom";
import { useFailureTagLabels } from "../failureTags";
import { ExportTranscriptsModal } from "../components/ExportTranscriptsModal";
import { RejudgeModal } from "../components/RejudgeModal";
import { EditCriteriaDrawer } from "../components/EditCriteriaDrawer";
import { RunOverviewTab } from "../components/RunOverviewTab";
import { buildCaseColumns } from "../components/caseColumns";
import { RunDashboardHeader } from "../components/RunDashboardHeader";
import { RunCaseResultsCard } from "../components/RunCaseResultsCard";
import { RunDiffTab } from "../components/RunDiffTab";
import { useRunDashboard } from "../hooks/useRunDashboard";

export default function RunDashboardPage() {
  const { runId } = useParams();
  const id = Number(runId);
  const tagLabel = useFailureTagLabels();
  const dash = useRunDashboard(id);

  if (dash.runError)
    return (
      <div className="dash-page">
        <Result
          status="warning"
          title="无法加载评测详情"
          subTitle={dash.runError}
          extra={
            <Button type="primary" onClick={() => dash.navigate("/runs")}>
              返回评测列表
            </Button>
          }
        />
      </div>
    );
  if (!dash.run) {
    return (
      <div className="dash-page" style={{ display: "grid", placeItems: "center", paddingTop: 80 }}>
        <Spin />
      </div>
    );
  }

  const columns = buildCaseColumns(id, tagLabel);

  return (
    <div className="dash-page">
      <RunDashboardHeader
        run={dash.run}
        editingName={dash.editingName}
        nameDraft={dash.nameDraft}
        savingName={dash.savingName}
        acting={dash.acting}
        onNameDraftChange={dash.setNameDraft}
        onStartEditName={dash.startEditName}
        onCommitName={dash.commitName}
        onRejudge={dash.openRejudge}
        onResume={dash.doResume}
        onTogglePin={dash.togglePin}
      />

      <Tabs
        className="dash-tabs"
        activeKey={dash.activeTab}
        onChange={dash.setActiveTab}
        items={[
          {
            key: "overview",
            label: "概览",
            children: (
              <RunOverviewTab run={dash.run} reviewStats={dash.reviewStats} />
            ),
          },
          {
            key: "detail",
            label: "用例明细",
            children: (
              <RunCaseResultsCard
                benchmarkName={dash.benchmarkName}
                reviewStats={dash.reviewStats}
                cases={dash.cases}
                shownCases={dash.shownCases}
                columns={columns}
                filters={dash.filters}
                setFilters={dash.setFilters}
                reviewFilter={dash.reviewFilter}
                setReviewFilter={dash.setReviewFilter}
                onlyPending={dash.onlyPending}
                setOnlyPending={dash.setOnlyPending}
                queueIds={dash.queueIds}
                hasActiveFilters={dash.hasActiveFilters}
                resetFilters={dash.resetFilters}
                exporting={dash.exporting}
                onOpenYamlEditor={dash.openYamlEditor}
                onOpenExport={() => dash.setExportOpen(true)}
              />
            ),
          },
          {
            key: "diff",
            label: "版本对比",
            children: (
              <RunDiffTab
                runId={id}
                otherRuns={dash.otherRuns}
                diff={dash.diff}
                diffBaselineId={dash.diffBaselineId}
                diffLoading={dash.diffLoading}
                currentCases={dash.diffCurrentCases.length ? dash.diffCurrentCases : dash.cases}
                baselineCases={dash.baselineCases}
                onSelectBaseline={dash.selectDiffBaseline}
              />
            ),
          },
        ]}
      />

      <ExportTranscriptsModal
        open={dash.exportOpen}
        caseCount={dash.cases.length}
        loading={dash.exporting}
        onOk={dash.doExport}
        onCancel={() => dash.setExportOpen(false)}
      />

      <RejudgeModal
        open={dash.rejudgeOpen}
        loading={dash.acting}
        form={dash.rejudgeForm}
        benchmarks={dash.benchmarks}
        judgeModels={dash.judgeModels}
        onOk={dash.submitRejudge}
        onCancel={() => dash.setRejudgeOpen(false)}
      />

      <EditCriteriaDrawer
        open={dash.yamlOpen}
        loading={dash.yamlActions.saving}
        isBuiltin={dash.isBuiltinBenchmark}
        benchmarkLabel={
          dash.run?.benchmark_id
            ? `#${dash.run.benchmark_id}「${
                dash.benchmarks.find((b) => b.id === dash.run!.benchmark_id)?.name ||
                dash.benchmarkName ||
                "—"
              }」`
            : undefined
        }
        name={dash.yamlName}
        onNameChange={dash.setYamlName}
        yamlText={dash.yamlText}
        onYamlChange={dash.setYamlText}
        yamlLoading={dash.yamlLoading}
        onClose={() => dash.setYamlOpen(false)}
        onSaveAs={dash.saveYamlAsBenchmark}
        onOverwrite={dash.saveYamlOverwrite}
      />

    </div>
  );
}
