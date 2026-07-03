import { useEffect, useState, type Key } from "react";
import { Descriptions, Drawer, Popconfirm, Space, Table, Typography } from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import type { ColumnsType, TableProps } from "antd/es/table";
import type { FilterValue } from "antd/es/table/interface";
import type { OnlineAnnotationPoolCase, OnlineAnnotationPoolPath } from "../api/index";
import {
  DimensionBars,
  DimensionFeedback,
  GateTag,
  GradeText,
  TaskTypeText,
} from "./OnlineEvalDisplay";
import { OnlineEvalConversation } from "./OnlineEvalConversation";
import {
  DashTableActions,
  DashTableDangerLink,
} from "./DashTableActions";
import {
  ONLINE_EVAL_GATE_FILTERS,
  ONLINE_EVAL_GRADE_FILTERS,
  ONLINE_EVAL_ROLE_SCORE_FILTERS,
  ONLINE_EVAL_SCORE_FILTERS,
  matchesOnlineEvalGateFilter,
  matchesOnlineEvalGradeFilter,
  matchesOnlineEvalRoleScoreFilter,
  matchesOnlineEvalScoreFilter,
} from "../utils/onlineEvalCaseFilters";

interface OnlineAnnotationPoolDetailDrawerProps {
  path: OnlineAnnotationPoolPath | null;
  cases: OnlineAnnotationPoolCase[];
  loading: boolean;
  deletingCaseId: number | null;
  onClose: () => void;
  onDeleteCase: (pathId: number, caseId: number) => Promise<void>;
}

interface AnnotationPoolCaseTableFilters {
  gate_status?: FilterValue | null;
  total_score?: FilterValue | null;
  doctor_score?: FilterValue | null;
  nurse_score?: FilterValue | null;
  patient_score?: FilterValue | null;
  grade?: FilterValue | null;
}

export function OnlineAnnotationPoolDetailDrawer({
  path,
  cases,
  loading,
  deletingCaseId,
  onClose,
  onDeleteCase,
}: OnlineAnnotationPoolDetailDrawerProps) {
  const [caseFilters, setCaseFilters] = useState<AnnotationPoolCaseTableFilters>({});

  useEffect(() => {
    setCaseFilters({});
  }, [path?.id]);

  const renderRoleScore = (
    row: OnlineAnnotationPoolCase,
    key: "doctor_score" | "nurse_score" | "patient_score"
  ) => {
    const value = row.score_breakdown?.[key];
    return <span className="mono">{typeof value === "number" ? value.toFixed(1) : "-"}</span>;
  };

  const roleScoreFilter = (key: "doctor_score" | "nurse_score" | "patient_score") => (
    value: boolean | Key,
    row: OnlineAnnotationPoolCase
  ) => matchesOnlineEvalRoleScoreFilter(value, row, key);

  const columns: ColumnsType<OnlineAnnotationPoolCase> = [
    {
      title: "Case 名称",
      dataIndex: "case_name",
      width: 260,
      ellipsis: true,
      render: (v: string, row) => v || row.user_text || row.external_id || `#${row.id}`,
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
      render: (v: string) => <GateTag value={v} />,
    },
    {
      title: "分数",
      dataIndex: "total_score",
      width: 100,
      filters: ONLINE_EVAL_SCORE_FILTERS,
      filteredValue: caseFilters.total_score ?? null,
      onFilter: matchesOnlineEvalScoreFilter,
      render: (v: number) => <span className="mono">{Number(v || 0).toFixed(1)}</span>,
    },
    {
      title: "医生端",
      key: "doctor_score",
      width: 110,
      filters: ONLINE_EVAL_ROLE_SCORE_FILTERS,
      filteredValue: caseFilters.doctor_score ?? null,
      onFilter: roleScoreFilter("doctor_score"),
      render: (_, row) => renderRoleScore(row, "doctor_score"),
    },
    {
      title: "护士端",
      key: "nurse_score",
      width: 110,
      filters: ONLINE_EVAL_ROLE_SCORE_FILTERS,
      filteredValue: caseFilters.nurse_score ?? null,
      onFilter: roleScoreFilter("nurse_score"),
      render: (_, row) => renderRoleScore(row, "nurse_score"),
    },
    {
      title: "患者端",
      key: "patient_score",
      width: 110,
      filters: ONLINE_EVAL_ROLE_SCORE_FILTERS,
      filteredValue: caseFilters.patient_score ?? null,
      onFilter: roleScoreFilter("patient_score"),
      render: (_, row) => renderRoleScore(row, "patient_score"),
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
      title: "操作",
      key: "actions",
      width: 100,
      fixed: "right",
      render: (_, row) => (
        <DashTableActions>
          <Popconfirm
            title="确认删除该 case？"
            description="删除后会从当前标注集中移除，且不可恢复。"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            disabled={deletingCaseId !== null}
            onConfirm={() => path && void onDeleteCase(path.id, row.id)}
          >
            <DashTableDangerLink disabled={deletingCaseId !== null}>
              <DeleteOutlined /> {deletingCaseId === row.id ? "删除中" : "删除"}
            </DashTableDangerLink>
          </Popconfirm>
        </DashTableActions>
      ),
    },
  ];

  const handleCaseTableChange: TableProps<OnlineAnnotationPoolCase>["onChange"] = (
    _pagination,
    filters
  ) => {
    setCaseFilters({
      gate_status: filters.gate_status ?? null,
      total_score: filters.total_score ?? null,
      doctor_score: filters.doctor_score ?? null,
      nurse_score: filters.nurse_score ?? null,
      patient_score: filters.patient_score ?? null,
      grade: filters.grade ?? null,
    });
  };

  const handleClose = () => {
    setCaseFilters({});
    onClose();
  };

  return (
    <Drawer
      title={path ? `标注集 · ${path.path}` : "标注集详情"}
      width={1020}
      open={Boolean(path)}
      onClose={handleClose}
    >
      {path ? (
        <Space direction="vertical" size={18} style={{ width: "100%" }}>
          <Descriptions bordered size="small" column={3}>
            <Descriptions.Item label="标注集">{path.path}</Descriptions.Item>
            <Descriptions.Item label="Case">{path.case_count}</Descriptions.Item>
            <Descriptions.Item label="创建人">{path.created_by || "-"}</Descriptions.Item>
            <Descriptions.Item label="描述" span={3}>
              {path.description || "-"}
            </Descriptions.Item>
          </Descriptions>
          <Table
            className="dash-table online-eval-case-table"
            rowKey="id"
            loading={loading}
            columns={columns}
            dataSource={cases}
            onChange={handleCaseTableChange}
            tableLayout="fixed"
            scroll={{ x: 1210 }}
            pagination={{ showTotal: (total) => `共 ${total} 条` }}
            expandable={{
              expandedRowRender: (row) => (
                <div className="online-eval-case-detail-window">
                  <div className="online-eval-case-detail-inner">
                    <Space direction="vertical" size={14} style={{ width: "100%" }}>
                      <Typography.Text strong>对话内容</Typography.Text>
                      <OnlineEvalConversation row={row} />
                      {row.gate_status !== "fail" && (
                        <>
                          <Typography.Text strong>维度分</Typography.Text>
                          <DimensionBars scores={row.dimension_scores} breakdown={row.score_breakdown} />
                          <Typography.Text strong>各维度依据、证据与建议</Typography.Text>
                          <DimensionFeedback row={row} />
                        </>
                      )}
                      <Typography.Text strong>
                        {row.gate_status === "fail" ? "Gate 失败证据与建议" : "全局证据与建议"}
                      </Typography.Text>
                      <ul>
                        {(row.evidence.length ? row.evidence : [{ tag: "empty", text: "暂无全局证据" }]).map((item, idx) => (
                          <li key={`${item.tag || "evidence"}-${idx}`}>{item.text}</li>
                        ))}
                        {(row.improvement_suggestions.length ? row.improvement_suggestions : ["暂无建议"]).map((item, idx) => (
                          <li key={`suggestion-${idx}`}>{item}</li>
                        ))}
                      </ul>
                    </Space>
                  </div>
                </div>
              ),
            }}
          />
        </Space>
      ) : null}
    </Drawer>
  );
}
