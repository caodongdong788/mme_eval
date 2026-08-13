import type { Dispatch, SetStateAction } from "react";
import { Button, Space, Table } from "antd";
import { BulbOutlined, DownloadOutlined, EditOutlined } from "@ant-design/icons";
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
  onOpenYamlEditor: () => void;
  onOpenExport: () => void;
  onStartAttribution: (cases: CaseRow[]) => void;
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
  onOpenYamlEditor,
  onOpenExport,
  onStartAttribution,
}: RunCaseResultsCardProps) {
  const failedShownCases = shownCases.filter((item) => !item.release_passed);
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
          <Space size={8} wrap>
            {live && (
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
          loading={loading}
          pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }}
        />
      </div>
    </div>
  );
}
