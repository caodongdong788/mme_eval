import type { Dispatch, SetStateAction } from "react";
import { Button, Progress, Space, Table } from "antd";
import { BulbOutlined, DownloadOutlined, EditOutlined, ReloadOutlined } from "@ant-design/icons";
import { type Key, useEffect, useMemo, useState } from "react";
import type { ColumnsType } from "antd/es/table";
import { CaseRow, ReviewStats } from "../api/index";
import type { CaseFilterCondition, CaseFilterValueOptions } from "../utils/caseFilters";
import { CaseFilterBuilder } from "./CaseFilterBuilder";

export interface RunCaseResultsCardProps {
  benchmarkName?: string;
  reviewStats: ReviewStats | null;
  cases: CaseRow[];
  shownCases: CaseRow[];
  columns: ColumnsType<CaseRow>;
  filterConditions: CaseFilterCondition[];
  setFilterConditions: Dispatch<SetStateAction<CaseFilterCondition[]>>;
  filterValueOptions: CaseFilterValueOptions;
  exporting: boolean;
  loading?: boolean;
  live?: boolean;
  retryProgress?: {
    done: number;
    total: number;
    status: string;
    cancelled?: boolean;
    sampleIds: string[];
    caseStates: Record<string, { status: "queued" | "running" | "waiting_for_judge" | "completed" | "cancelled"; percent?: number }>;
  };
  onOpenYamlEditor: () => void;
  onOpenExport: () => void;
  onStartAttribution: (cases: CaseRow[]) => void;
  onRetryCases: (cases: CaseRow[]) => void;
  onCancelRetry: () => void;
}

export function RunCaseResultsCard({
  benchmarkName,
  reviewStats,
  cases,
  shownCases,
  columns,
  filterConditions,
  setFilterConditions,
  filterValueOptions,
  exporting,
  loading = false,
  live = false,
  retryProgress,
  onOpenYamlEditor,
  onOpenExport,
  onStartAttribution,
  onRetryCases,
  onCancelRetry,
}: RunCaseResultsCardProps) {
  const [selectedKeys, setSelectedKeys] = useState<Key[]>([]);
  const failedShownCases = shownCases.filter((item) => !item.release_passed);
  const selectedCases = useMemo(
    () => shownCases.filter((item) => selectedKeys.includes(item.id)),
    [selectedKeys, shownCases],
  );
  useEffect(() => {
    const visible = new Set(shownCases.map((item) => item.id));
    setSelectedKeys((keys) => keys.filter((key) => visible.has(Number(key))));
  }, [shownCases]);
  const retryActive = Boolean(
    retryProgress && !retryProgress.cancelled && ["pending", "running"].includes(retryProgress.status),
  );
  const displayColumns = useMemo<ColumnsType<CaseRow>>(() => {
    if (!retryProgress) return columns;
    const retryColumn: ColumnsType<CaseRow>[number] = {
      key: "retry_progress",
      title: "重新评测进度",
      width: 190,
      render: (_value, row) => {
        const state = retryProgress.caseStates[row.sample_id]
          || (retryProgress.sampleIds.includes(row.sample_id)
            ? { status: "queued" as const, percent: 0 }
            : undefined);
        if (!state) return <span className="muted">—</span>;
        const label = state.status === "completed"
          ? "已完成"
          : state.status === "cancelled"
            ? "已取消"
            : state.status === "waiting_for_judge"
              ? "等待判分"
              : state.status === "running"
              ? "评测中"
              : "排队中";
        const percent = state.status === "completed" ? 100 : Math.max(0, state.percent || 0);
        return (
          <div className={`case-retry-cell case-retry-cell--${state.status}`}>
            <Progress percent={percent} showInfo={false} size="small" status={state.status === "cancelled" ? "exception" : undefined} />
            <span>{label}</span>
          </div>
        );
      },
    };
    return [...columns, retryColumn];
  }, [columns, retryProgress]);
  return (
    <div className="run-detail-page">
      <div className="dash-table-card">
        <div className="dash-table-card__head">
          <div className="run-case-results__heading">
            <h3>用例结果</h3>
            {benchmarkName && (
              <span className="dash-table-card__sub">{benchmarkName}</span>
            )}
          </div>
          <Space size={8} wrap className="run-case-results__actions">
            {live && !retryProgress && (
              <span className="status-dot status-dot--running">
                实时更新 · 已完成 {cases.length} 条
              </span>
            )}
            <CaseFilterBuilder
              conditions={filterConditions}
              onChange={setFilterConditions}
              valueOptions={filterValueOptions}
            />
            {reviewStats && reviewStats.queue_total > 0 && (
              <span className="status-dot status-dot--warn">
                待审 {reviewStats.pending}/{reviewStats.queue_total}
              </span>
            )}
            <Button
              icon={<BulbOutlined />}
              onClick={() => onStartAttribution(shownCases)}
              disabled={live || failedShownCases.length === 0}
              title={
                failedShownCases.length
                  ? `对当前筛选命中的 ${failedShownCases.length} 条不合格用例发起归因分析`
                  : "当前筛选结果没有不合格用例"
              }
            >
              开始归因分析{failedShownCases.length ? ` (${failedShownCases.length})` : ""}
            </Button>
            {retryActive ? (
              <Button danger onClick={onCancelRetry} loading={loading}>
                终止评测
              </Button>
            ) : (
              <Button
                icon={<ReloadOutlined />}
                onClick={() => onRetryCases(selectedCases)}
                disabled={live || selectedCases.length === 0}
                title={
                  selectedCases.length
                    ? `重新执行选中的 ${selectedCases.length} 条用例，并原位覆盖结果`
                    : "请先勾选需要重新评测的用例"
                }
              >
                重新评测{selectedCases.length ? ` (${selectedCases.length})` : ""}
              </Button>
            )}
            <Button
              icon={<EditOutlined />}
              onClick={onOpenYamlEditor}
              disabled={cases.length === 0}
              title="把当前过滤命中的用例完整 YAML 打开在线改判据，另存为新 benchmark"
            >
              编辑判据(YAML)
            </Button>
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              loading={exporting}
              onClick={onOpenExport}
              disabled={cases.length === 0}
            >
              导出对话流水(飞书)
            </Button>
          </Space>
        </div>
        <Table
          className="dash-table"
          rowKey="id"
          size="small"
          tableLayout="auto"
          columns={displayColumns}
          dataSource={shownCases}
          rowSelection={{
            selectedRowKeys: selectedKeys,
            onChange: (keys) => setSelectedKeys(keys),
            getCheckboxProps: () => ({ disabled: live }),
          }}
          loading={loading}
          pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }}
        />
      </div>
    </div>
  );
}
