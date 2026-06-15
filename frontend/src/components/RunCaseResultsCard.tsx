import { Dispatch, SetStateAction } from "react";
import { Button, Card, Space, Table } from "antd";
import { DownloadOutlined, EditOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { CaseRow, ReviewStats } from "../api";
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
    <Card
      title={
        <span style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
          用例结果
          {benchmarkName && (
            <span style={{ fontSize: 12.5, fontWeight: 500, color: "var(--muted)" }}>
              benchmark · {benchmarkName}
            </span>
          )}
        </span>
      }
      size="small"
      extra={
        <Space size={8}>
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
            icon={<DownloadOutlined />}
            loading={exporting}
            onClick={onOpenExport}
            disabled={cases.length === 0}
          >
            导出对话流水(飞书)
          </Button>
        </Space>
      }
    >
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
        rowKey="id"
        size="small"
        tableLayout="auto"
        columns={columns}
        dataSource={shownCases}
        pagination={{ pageSize: 20 }}
      />
    </Card>
  );
}
