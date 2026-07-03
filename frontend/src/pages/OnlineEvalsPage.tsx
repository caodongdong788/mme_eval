import {
  Alert,
  Button,
  Form,
  Input,
  Popconfirm,
  Select,
  Space,
  Table,
  Tabs,
  Tooltip,
} from "antd";
import {
  DeleteOutlined,
  FileSearchOutlined,
  FolderAddOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import type { OnlineEval } from "../api/index";
import { AsyncLoadError } from "../components/AsyncLoadError";
import { DashPanel } from "../components/DashPanel";
import {
  DashTableActions,
  DashTableDangerLink,
  DashTableLink,
} from "../components/DashTableActions";
import { DashboardPageShell } from "../components/DashboardPageShell";
import { OnlineAnnotationPoolDetailDrawer } from "../components/OnlineAnnotationPoolDetailDrawer";
import { OnlineAnnotationPoolTable } from "../components/OnlineAnnotationPoolTable";
import {
  AverageScoreText,
  OnlineEvalStatusCell,
} from "../components/OnlineEvalDisplay";
import { OnlineEvalDetailDrawer } from "../components/OnlineEvalDetailDrawer";
import { useOnlineEvalsPage } from "../hooks/useOnlineEvalsPage";

export default function OnlineEvalsPage() {
  const vm = useOnlineEvalsPage();

  const columns: ColumnsType<OnlineEval> = [
    { title: "ID", dataIndex: "id", width: 70 },
    {
      title: "评测名称",
      dataIndex: "name",
      width: 220,
      ellipsis: true,
      render: (v: string, row) => {
        const text = v || `线上评测 #${row.id}`;
        return <Tooltip title={text}>{text}</Tooltip>;
      },
    },
    {
      title: "备注",
      dataIndex: "note",
      width: 220,
      ellipsis: true,
      render: (v: string) =>
        v ? <Tooltip title={v}>{v}</Tooltip> : <span style={{ color: "var(--muted)" }}>-</span>,
    },
    {
      title: "Benchmark",
      dataIndex: "benchmark_id",
      width: 180,
      render: (id: number | null) =>
        id ? vm.benchmarkNameById[id] || `#${id}` : <span style={{ color: "var(--muted)" }}>-</span>,
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 170,
      render: (_status: string, row) => (
        <OnlineEvalStatusCell row={row} progress={vm.progress[row.id]} />
      ),
    },
    {
      title: "平均分",
      dataIndex: "avg_score",
      width: 110,
      render: (v: number, row) =>
        <AverageScoreText value={v} ready={row.status === "success" || v > 0} />,
    },
    { title: "Case", dataIndex: "case_count", width: 80 },
    { title: "Judge", dataIndex: "judge_model", width: 150, render: (v: string) => v || "默认" },
    { title: "Gate Fail", dataIndex: "gate_fail_count", width: 110 },
    { title: "需人审", dataIndex: "needs_review_count", width: 90 },
    {
      title: "操作",
      key: "actions",
      width: 170,
      fixed: "right",
      render: (_, row) => {
        const busy = row.status === "pending" || row.status === "running";
        return (
          <DashTableActions>
            <DashTableLink onClick={() => vm.openDetail(row.id)}>详情</DashTableLink>
            <Popconfirm
              title="确认删除该线上评测？"
              description="将一并删除该记录下的 case 结果，且不可恢复。"
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={() => void vm.deleteEval(row.id)}
              disabled={busy}
            >
              <DashTableDangerLink disabled={busy}>
                <DeleteOutlined /> 删除
              </DashTableDangerLink>
            </Popconfirm>
          </DashTableActions>
        );
      },
    },
  ];

  return (
    <DashboardPageShell
      title="线上评测"
      sub="选择来源为线上的 benchmark，对真实线上对话做陪伴型质检评分"
    >
      <Tabs
        className="dash-tabs"
        items={[
          {
            key: "evals",
            label: "评测任务",
            children: (
              <>
                <DashPanel title="创建线上评测">
                  {vm.onlineBenchmarks.length === 0 ? (
                    <Alert
                      type="warning"
                      showIcon
                      style={{ marginBottom: 16 }}
                      message="暂无线上 benchmark。请先在 Benchmark 库通过飞书 URL 或 JSONL 创建「线上」benchmark。"
                    />
                  ) : null}
                  <Form form={vm.form} layout="vertical">
                    <div className="online-eval-form-grid">
                      <Form.Item name="name" label="评测名称" rules={[{ required: true, message: "请输入评测名称" }]}>
                        <Input placeholder="如：骨健康线上样本" />
                      </Form.Item>
                      <Form.Item
                        name="benchmark_id"
                        label="线上 Benchmark"
                        rules={[{ required: true, message: "请选择线上 benchmark" }]}
                        extra="仅展示来源标签为「线上」的 benchmark。评测会使用该 benchmark 中全部 Q&A。"
                      >
                        <Select
                          showSearch
                          optionFilterProp="label"
                          placeholder="选择线上 benchmark"
                          options={vm.onlineBenchmarks.map((b) => ({
                            value: b.id,
                            label: `${b.name}（线上 · ${b.case_count} 条）`,
                          }))}
                        />
                      </Form.Item>
                    </div>
                    <Form.Item
                      name="judge_model_id"
                      label="Judge 模型"
                      extra="不选择时使用 config.yaml 中 judges.llm 的默认模型"
                    >
                      <Select
                        allowClear
                        placeholder="默认 judge 模型"
                        options={vm.judgeModels.map((m) => ({
                          value: m.id,
                          label: `${m.name} · ${m.model}`,
                        }))}
                      />
                    </Form.Item>
                    <Form.Item name="note" label="备注">
                      <Input.TextArea rows={2} placeholder="本次线上质检的背景或批次说明" />
                    </Form.Item>
                    <Button
                      type="primary"
                      icon={<FileSearchOutlined />}
                      loading={vm.submitting}
                      disabled={vm.onlineBenchmarks.length === 0}
                      onClick={vm.submit}
                    >
                      创建线上评测
                    </Button>
                  </Form>
                </DashPanel>

                <div className="dash-table-card">
                  {vm.loadError ? (
                    <AsyncLoadError message={vm.loadError} onRetry={vm.reload} />
                  ) : (
                    <Table
                      className="dash-table"
                      rowKey="id"
                      loading={vm.loading}
                      columns={columns}
                      dataSource={vm.rows}
                      scroll={{ x: 1180 }}
                      pagination={{ showTotal: (t) => `共 ${t} 条` }}
                    />
                  )}
                </div>
              </>
            ),
          },
          {
            key: "pool",
            label: "标注池",
            children: (
              <DashPanel title="标注池">
                <Form form={vm.poolPathForm} layout="vertical">
                  <div className="online-pool-form-grid">
                    <Form.Item
                      name="path"
                      label="标注集"
                      rules={[{ required: true, message: "请输入标注集名称" }]}
                    >
                      <Input placeholder="如：骨健康满意样本" />
                    </Form.Item>
                    <Form.Item name="description" label="描述">
                      <Input placeholder="标注集用途说明" />
                    </Form.Item>
                    <Form.Item name="source_url" label="飞书 URL">
                      <Input placeholder="粘贴飞书表格 URL，导入所有 tab" />
                    </Form.Item>
                    <Form.Item label=" ">
                      <Space wrap>
                        <Button
                          type="primary"
                          icon={<FolderAddOutlined />}
                          loading={vm.poolSubmitting}
                          disabled={vm.poolImporting}
                          onClick={vm.createPoolPath}
                        >
                          新增标注集
                        </Button>
                        <Button
                          icon={<UploadOutlined />}
                          loading={vm.poolImporting}
                          disabled={vm.poolSubmitting}
                          onClick={vm.importPoolPathFromFeishu}
                        >
                          飞书导入
                        </Button>
                      </Space>
                    </Form.Item>
                  </div>
                </Form>
                {vm.poolError ? (
                  <AsyncLoadError message={vm.poolError} onRetry={vm.reloadPoolPaths} />
                ) : (
                  <OnlineAnnotationPoolTable
                    loading={vm.poolLoading}
                    rows={vm.poolPaths}
                    exportingPathId={vm.poolExportingPathId}
                    editingPath={vm.poolEditingPath}
                    updatingPathId={vm.poolUpdatingPathId}
                    deletingPathId={vm.poolDeletingPathId}
                    onExport={(pathId) => void vm.exportPoolPath(pathId)}
                    onOpenDetail={(row) => void vm.openPoolPathDetail(row)}
                    onEdit={vm.openPoolPathEdit}
                    onEditCancel={vm.closePoolPathEdit}
                    onEditSubmit={vm.updatePoolPath}
                    onDelete={(pathId) => void vm.deletePoolPath(pathId)}
                  />
                )}
              </DashPanel>
            ),
          },
        ]}
      />

      <OnlineEvalDetailDrawer
        detail={vm.detail}
        detailLoading={vm.detailLoading}
        benchmarkNameById={vm.benchmarkNameById}
        poolPaths={vm.poolPaths}
        poolAddingCaseId={vm.poolAddingCaseId}
        deletingCaseId={vm.deletingCaseId}
        rescoringCaseId={vm.rescoringCaseId}
        onClose={vm.closeDetail}
        onAddCaseToPool={vm.addCaseToPool}
        onDeleteCase={vm.deleteCase}
        onRescoreCase={vm.rescoreCase}
      />
      <OnlineAnnotationPoolDetailDrawer
        path={vm.poolDetailPath}
        cases={vm.poolDetailCases}
        loading={vm.poolDetailLoading}
        deletingCaseId={vm.poolDeletingCaseId}
        onClose={vm.closePoolPathDetail}
        onDeleteCase={vm.deletePoolCase}
      />
    </DashboardPageShell>
  );
}
