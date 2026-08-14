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
  retryProgress?: { done: number; total: number; status: string };
  onOpenYamlEditor: () => void;
  onOpenExport: () => void;
  onStartAttribution: (cases: CaseRow[]) => void;
  onRetryCases: (cases: CaseRow[]) => void;
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
  const retryPercent = retryProgress?.total
    ? Math.round(Math.min(retryProgress.done / retryProgress.total, 1) * 100)
    : 0;
  const retryStateLabel = retryProgress?.status === "success"
    ? "已完成"
    : retryProgress?.status === "failed"
      ? "重新评测失败"
      : "重新评测中";
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
            {retryProgress ? (
              <div className="case-retry-progress" role="status" aria-label="重新评测进度">
                <span className="case-retry-progress__title">重新评测</span>
                <Progress
                  percent={retryPercent}
                  showInfo={false}
                  size="small"
                  status={retryProgress.status === "failed" ? "exception" : undefined}
                />
                <span className="case-retry-progress__value">
                  {retryStateLabel} {retryProgress.done}/{retryProgress.total}
                </span>
                {retryProgress.status !== "pending" && retryProgress.status !== "running" && (
                  <Button
                    type="link"
                    size="small"
                    icon={<ReloadOutlined />}
                    onClick={() => onRetryCases(selectedCases)}
                    disabled={selectedCases.length === 0}
                  >
                    再次评测
                  </Button>
                )}
              </div>
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
          columns={columns}
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
