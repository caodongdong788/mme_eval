import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Descriptions,
  Drawer,
  Modal,
  Space,
  Table,
  Typography,
} from "antd";
import { DownloadOutlined, FileSearchOutlined } from "@ant-design/icons";
import type { ColumnsType, TableProps } from "antd/es/table";
import type { FilterValue } from "antd/es/table/interface";
import type { OnlineEvalDetail, OnlineEvalCase } from "../api/index";
import {
  AverageScoreText,
  DimensionBars,
  DimensionFeedback,
  GateTag,
  GradeText,
  RiskTags,
  StatusTag,
  TaskTypeText,
} from "./OnlineEvalDisplay";
import {
  ONLINE_EVAL_GATE_FILTERS,
  ONLINE_EVAL_GRADE_FILTERS,
  ONLINE_EVAL_SCORE_FILTERS,
  type OnlineEvalCaseExportFilters,
  filterOnlineEvalCasesBySelection,
  matchesOnlineEvalGateFilter,
  matchesOnlineEvalGradeFilter,
  matchesOnlineEvalScoreFilter,
} from "../utils/onlineEvalCaseFilters";

interface OnlineEvalCaseTableFilters {
  gate_status?: FilterValue | null;
  total_score_10?: FilterValue | null;
  grade?: FilterValue | null;
}

interface OnlineEvalDetailDrawerProps {
  detail: OnlineEvalDetail | null;
  detailLoading: boolean;
  benchmarkNameById: Record<number, string>;
  exporting: boolean;
  onClose: () => void;
  onExport: (filters: OnlineEvalCaseExportFilters) => Promise<boolean>;
}

function filterValues(value?: FilterValue | null): string[] {
  return (value ?? []).map(String);
}

export function OnlineEvalDetailDrawer({
  detail,
  detailLoading,
  benchmarkNameById,
  exporting,
  onClose,
  onExport,
}: OnlineEvalDetailDrawerProps) {
  const [caseFilters, setCaseFilters] = useState<OnlineEvalCaseTableFilters>({});
  const [exportOpen, setExportOpen] = useState(false);

  useEffect(() => {
    setCaseFilters({});
    setExportOpen(false);
  }, [detail?.id]);

  const exportFilters = useMemo<OnlineEvalCaseExportFilters>(
    () => ({
      gate_status: filterValues(caseFilters.gate_status),
      score_bucket: filterValues(caseFilters.total_score_10),
      grade: filterValues(caseFilters.grade),
    }),
    [caseFilters]
  );
  const filteredCases = useMemo(
    () => filterOnlineEvalCasesBySelection(detail?.cases ?? [], exportFilters),
    [detail?.cases, exportFilters]
  );

  const caseColumns: ColumnsType<OnlineEvalCase> = [
    {
      title: "Case 名称",
      dataIndex: "case_name",
      width: 260,
      ellipsis: true,
      render: (v: string, r) => v || r.user_text || r.external_id || `#${r.id}`,
    },
    {
      title: "类型",
      dataIndex: "task_type",
      width: 150,
      render: (v: string) => <TaskTypeText value={v} />,
    },
    {
      title: "Gate",
      dataIndex: "gate_status",
      width: 100,
      filters: ONLINE_EVAL_GATE_FILTERS,
      filteredValue: caseFilters.gate_status ?? null,
      onFilter: matchesOnlineEvalGateFilter,
      render: (v) => <GateTag value={v} />,
    },
    {
      title: "分数",
      dataIndex: "total_score_10",
      width: 100,
      filters: ONLINE_EVAL_SCORE_FILTERS,
      filteredValue: caseFilters.total_score_10 ?? null,
      onFilter: matchesOnlineEvalScoreFilter,
      render: (v: number) => <span className="mono">{v.toFixed(1)}</span>,
    },
    {
      title: "评级",
      dataIndex: "grade",
      width: 120,
      filters: ONLINE_EVAL_GRADE_FILTERS,
      filteredValue: caseFilters.grade ?? null,
      onFilter: matchesOnlineEvalGradeFilter,
      render: (v: string) => <GradeText value={v} />,
    },
    {
      title: "风险点",
      dataIndex: "risk_tags",
      render: (tags: string[]) => <RiskTags tags={tags} />,
    },
  ];

  const handleCaseTableChange: TableProps<OnlineEvalCase>["onChange"] = (
    _pagination,
    filters
  ) => {
    setCaseFilters({
      gate_status: filters.gate_status ?? null,
      total_score_10: filters.total_score_10 ?? null,
      grade: filters.grade ?? null,
    });
  };

  const handleClose = () => {
    setCaseFilters({});
    setExportOpen(false);
    onClose();
  };

  const handleExport = async () => {
    const ok = await onExport(exportFilters);
    if (ok) setExportOpen(false);
  };

  return (
    <>
      <Drawer
        title={detail ? `线上评测 #${detail.id} · ${detail.name}` : "线上评测详情"}
        width={920}
        open={Boolean(detail) || detailLoading}
        onClose={handleClose}
        extra={
          detail ? (
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              loading={exporting}
              disabled={detail.cases.length === 0}
              onClick={() => setExportOpen(true)}
            >
              导出清单(飞书)
            </Button>
          ) : null
        }
      >
        {detail ? (
          <Space direction="vertical" size={18} style={{ width: "100%" }}>
            <Descriptions bordered size="small" column={4}>
              <Descriptions.Item label="状态"><StatusTag value={detail.status} /></Descriptions.Item>
              <Descriptions.Item label="平均分">
                <AverageScoreText
                  value={detail.avg_score_10}
                  cases={detail.cases}
                  ready={detail.status === "success" || detail.avg_score_10 > 0}
                />
              </Descriptions.Item>
              <Descriptions.Item label="Case">{detail.case_count}</Descriptions.Item>
              <Descriptions.Item label="Gate Fail">{detail.gate_fail_count}</Descriptions.Item>
              <Descriptions.Item label="需人审">{detail.needs_review_count}</Descriptions.Item>
              <Descriptions.Item label="Benchmark">
                {detail.benchmark_id
                  ? benchmarkNameById[detail.benchmark_id] || `#${detail.benchmark_id}`
                  : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="Judge">{detail.judge_model || "默认"}</Descriptions.Item>
            </Descriptions>
            <Table
              className="dash-table"
              rowKey="id"
              columns={caseColumns}
              dataSource={detail.cases}
              onChange={handleCaseTableChange}
              expandable={{
                expandedRowRender: (row) => (
                  <Space direction="vertical" size={14} style={{ width: "100%" }}>
                    <Typography.Text strong>用户原文</Typography.Text>
                    <Typography.Paragraph style={{ whiteSpace: "pre-wrap" }}>
                      {row.user_text || "-"}
                    </Typography.Paragraph>
                    <Typography.Text strong>Bot 回复</Typography.Text>
                    <Typography.Paragraph style={{ whiteSpace: "pre-wrap" }}>
                      {row.assistant_text || "-"}
                    </Typography.Paragraph>
                    <Typography.Text strong>维度分</Typography.Text>
                    <DimensionBars scores={row.dimension_scores} />
                    <Typography.Text strong>各维度依据、证据与建议</Typography.Text>
                    <DimensionFeedback row={row} />
                    <Typography.Text strong>全局证据与建议</Typography.Text>
                    <ul>
                      {row.evidence.map((e, idx) => (
                        <li key={`${e.tag}-${idx}`}>{e.text}</li>
                      ))}
                      {row.improvement_suggestions.map((s, idx) => (
                        <li key={`suggestion-${idx}`}>{s}</li>
                      ))}
                    </ul>
                  </Space>
                ),
              }}
            />
          </Space>
        ) : (
          <FileSearchOutlined />
        )}
      </Drawer>
      <Modal
        title="导出评测清单到飞书"
        open={exportOpen}
        okText="导出"
        cancelText="取消"
        confirmLoading={exporting}
        okButtonProps={{ disabled: filteredCases.length === 0 }}
        onOk={() => void handleExport()}
        onCancel={() => setExportOpen(false)}
      >
        <p style={{ marginBottom: 0 }}>
          将按当前筛选条件导出 {filteredCases.length} 条线上对话，每条对话一行，多轮内容按第几轮展开为用户输入和 Cx 输出。
        </p>
      </Modal>
    </>
  );
}
