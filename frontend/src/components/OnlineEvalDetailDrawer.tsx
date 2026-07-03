import { useEffect, useState, type Key } from "react";
import {
  Descriptions,
  Drawer,
  Popconfirm,
  Select,
  Space,
  Table,
  Typography,
} from "antd";
import { DeleteOutlined, FileSearchOutlined, ReloadOutlined } from "@ant-design/icons";
import type { ColumnsType, TableProps } from "antd/es/table";
import type { FilterValue } from "antd/es/table/interface";
import type { OnlineAnnotationPoolPath, OnlineEvalDetail, OnlineEvalCase } from "../api/index";
import {
  DashTableActions,
  DashTableDangerLink,
  DashTableLink,
} from "./DashTableActions";
import {
  AverageScoreText,
  DimensionBars,
  DimensionFeedback,
  GateTag,
  GradeText,
  StatusTag,
  TaskTypeText,
} from "./OnlineEvalDisplay";
import { OnlineEvalConversation } from "./OnlineEvalConversation";
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

interface OnlineEvalCaseTableFilters {
  gate_status?: FilterValue | null;
  total_score?: FilterValue | null;
  doctor_score?: FilterValue | null;
  nurse_score?: FilterValue | null;
  patient_score?: FilterValue | null;
  grade?: FilterValue | null;
}

interface OnlineEvalDetailDrawerProps {
  detail: OnlineEvalDetail | null;
  detailLoading: boolean;
  benchmarkNameById: Record<number, string>;
  poolPaths: OnlineAnnotationPoolPath[];
  poolAddingCaseId: number | null;
  deletingCaseId: number | null;
  rescoringCaseId: number | null;
  onClose: () => void;
  onAddCaseToPool: (caseId: number, pathId: number) => Promise<void>;
  onDeleteCase: (evalId: number, caseId: number) => Promise<void>;
  onRescoreCase: (evalId: number, caseId: number) => Promise<void>;
}

export function OnlineEvalDetailDrawer({
  detail,
  detailLoading,
  benchmarkNameById,
  poolPaths,
  poolAddingCaseId,
  deletingCaseId,
  rescoringCaseId,
  onClose,
  onAddCaseToPool,
  onDeleteCase,
  onRescoreCase,
}: OnlineEvalDetailDrawerProps) {
  const [caseFilters, setCaseFilters] = useState<OnlineEvalCaseTableFilters>({});

  useEffect(() => {
    setCaseFilters({});
  }, [detail?.id]);

  const renderRoleScore = (
    row: OnlineEvalCase,
    key: "doctor_score" | "nurse_score" | "patient_score"
  ) => {
    const value = row.score_breakdown?.[key];
    return <span className="mono">{typeof value === "number" ? value.toFixed(1) : "-"}</span>;
  };

  const roleScoreFilter = (key: "doctor_score" | "nurse_score" | "patient_score") => (
    value: boolean | Key,
    row: OnlineEvalCase
  ) => matchesOnlineEvalRoleScoreFilter(value, row, key);

  const renderPoolSelect = (row: OnlineEvalCase) => (
    <div className="online-eval-pool-select">
      <Select
        size="small"
        style={{ width: "100%" }}
        placeholder={poolPaths.length ? "加入标注集" : "先建标注集"}
        disabled={poolPaths.length === 0}
        loading={poolAddingCaseId === row.id}
        value={undefined}
        options={poolPaths.map((item) => ({
          value: item.id,
          label: item.path,
        }))}
        onChange={(pathId: number) => void onAddCaseToPool(row.id, pathId)}
      />
    </div>
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
      dataIndex: "total_score",
      width: 100,
      filters: ONLINE_EVAL_SCORE_FILTERS,
      filteredValue: caseFilters.total_score ?? null,
      onFilter: matchesOnlineEvalScoreFilter,
      render: (v: number) => <span className="mono">{v.toFixed(1)}</span>,
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
      width: 320,
      fixed: "right",
      render: (_, row) => {
        const busy = detail?.status === "pending" || detail?.status === "running";
        const deleting = deletingCaseId === row.id;
        const rescoring = rescoringCaseId === row.id;
        const actionDisabled = busy || deletingCaseId !== null || rescoringCaseId !== null;
        return (
          <DashTableActions>
            {renderPoolSelect(row)}
            {rescoring ? (
              <div
                className="online-eval-rescore-progress"
                role="progressbar"
                aria-label="正在重新评测"
                aria-busy="true"
              >
                <span className="online-eval-rescore-progress__track" />
                <span className="online-eval-rescore-progress__text">重新评测中</span>
              </div>
            ) : (
              <DashTableLink
                disabled={actionDisabled}
                onClick={() => detail && void onRescoreCase(detail.id, row.id)}
              >
                <ReloadOutlined /> 重新评测
              </DashTableLink>
            )}
            <Popconfirm
              title="确认删除该 case？"
              description="删除后会从当前线上评测详情和汇总中移除，且不可恢复。"
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              disabled={actionDisabled}
              onConfirm={() => detail && void onDeleteCase(detail.id, row.id)}
            >
              <DashTableDangerLink disabled={actionDisabled}>
                <DeleteOutlined /> {deleting ? "删除中" : "删除"}
              </DashTableDangerLink>
            </Popconfirm>
          </DashTableActions>
        );
      },
    },
  ];

  const handleCaseTableChange: TableProps<OnlineEvalCase>["onChange"] = (
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
      title={detail ? `线上评测 #${detail.id} · ${detail.name}` : "线上评测详情"}
      width={1020}
      open={Boolean(detail) || detailLoading}
      onClose={handleClose}
    >
        {detail ? (
          <Space direction="vertical" size={18} style={{ width: "100%" }}>
            <Descriptions bordered size="small" column={4}>
              <Descriptions.Item label="状态"><StatusTag value={detail.status} /></Descriptions.Item>
              <Descriptions.Item label="平均分">
                <AverageScoreText
                  value={detail.avg_score}
                  cases={detail.cases}
                  ready={detail.status === "success" || detail.avg_score > 0}
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
              className="dash-table online-eval-case-table"
              rowKey="id"
              columns={caseColumns}
              dataSource={detail.cases}
              onChange={handleCaseTableChange}
              tableLayout="fixed"
              scroll={{ x: 1430 }}
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
                          {(row.evidence.length ? row.evidence : [{ tag: "empty", text: "暂无全局证据" }]).map((e, idx) => (
                            <li key={`${e.tag}-${idx}`}>{e.text}</li>
                          ))}
                          {(row.improvement_suggestions.length ? row.improvement_suggestions : ["暂无建议"]).map((s, idx) => (
                            <li key={`suggestion-${idx}`}>{s}</li>
                          ))}
                        </ul>
                      </Space>
                    </div>
                  </div>
                ),
              }}
            />
          </Space>
        ) : (
          <FileSearchOutlined />
        )}
    </Drawer>
  );
}
