import { Dispatch, SetStateAction } from "react";
import { Button, Space, Table } from "antd";
import { DownloadOutlined, EditOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { CaseRow, ReviewStats } from "../api/index";
import { CaseFilters, FilterToolbar } from "./FilterToolbar";

export interface RunCaseResultsCardProps {
  benchmarkName?: string;
  reviewStats: ReviewStats | null;
  cases: CaseRow[];
  shownCases: CaseRow[];
  columns: ColumnsType<CaseRow>;
  filters: CaseFilters;
  setFilters: Dispatch<SetStateAction<CaseFilters>>;
  reviewFilter?: string;
  setReviewFilter: (value: string | undefined) => void;
  onlyPending: boolean;
  setOnlyPending: (checked: boolean) => void;
  queueIds: Set<string>;
  hasActiveFilters: boolean;
  resetFilters: () => void;
  exporting: boolean;
  onOpenYamlEditor: () => void;
  onOpenExport: () => void;
}

export function RunCaseResultsCard({
  benchmarkName,
  reviewStats,
  cases,
  shownCases,
  columns,
  filters,
  setFilters,
  reviewFilter,
  setReviewFilter,
  onlyPending,
  setOnlyPending,
  queueIds,
  hasActiveFilters,
  resetFilters,
  exporting,
  onOpenYamlEditor,
  onOpenExport,
}: RunCaseResultsCardProps) {
  return (
    <div className="run-detail-page">
      <div className="dash-table-card">
        <div className="dash-table-card__head">
          <div>
            <h3>用例结果</h3>
            {benchmarkName && (
              <span className="dash-table-card__sub">benchmark · {benchmarkName}</span>
            )}
          </div>
          <Space size={8} wrap>
            {reviewStats && reviewStats.queue_total > 0 && (
              <span className="status-dot status-dot--warn">
                待审 {reviewStats.pending}/{reviewStats.queue_total}
              </span>
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
        <FilterToolbar
          filters={filters}
          setFilters={setFilters}
          reviewFilter={reviewFilter}
          setReviewFilter={setReviewFilter}
          onlyPending={onlyPending}
          setOnlyPending={setOnlyPending}
          queueIds={queueIds}
          hasActiveFilters={hasActiveFilters}
          resetFilters={resetFilters}
        />
        <Table
          className="dash-table"
          rowKey="id"
          size="small"
          tableLayout="auto"
          columns={columns}
          dataSource={shownCases}
          pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }}
        />
      </div>
    </div>
  );
}
