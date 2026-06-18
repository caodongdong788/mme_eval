import {
  Button,
  Popconfirm,
  Table,
  Typography,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { JudgeModel } from "../api/index";
import { AsyncLoadError } from "../components/AsyncLoadError";
import { DashTableActions, DashTableDangerLink, DashTableLink } from "../components/DashTableActions";
import { DashboardPageShell } from "../components/DashboardPageShell";
import { JudgeModelEditModal } from "../components/JudgeModelEditModal";
import { useJudgeModelsPage } from "../hooks/useJudgeModelsPage";

export default function JudgeModelsPage() {
  const jm = useJudgeModelsPage();

  const columns = [
    { title: "ID", dataIndex: "id", width: 60 },
    { title: "名称", dataIndex: "name" },
    { title: "Provider", dataIndex: "provider", width: 100 },
    {
      title: "模型",
      dataIndex: "model",
      render: (m: string) => <span className="mono">{m}</span>,
    },
    {
      title: "Base URL",
      dataIndex: "base_url",
      render: (u: string) =>
        u ? <span className="mono">{u}</span> : <Typography.Text type="secondary">默认</Typography.Text>,
    },
    {
      title: "对比并发",
      dataIndex: "pairwise_concurrency",
      width: 90,
      render: (n: number) => <span className="mono">{n ?? 4}</span>,
    },
    {
      title: "API Key",
      dataIndex: "has_api_key",
      width: 110,
      render: (has: boolean) =>
        has ? (
          <span className="status-dot status-dot--pass">已配置</span>
        ) : (
          <span className="status-dot status-dot--muted">未配置</span>
        ),
    },
    {
      title: "创建人",
      dataIndex: "created_by",
      width: 110,
      render: (v: string | null) => v || <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: "操作",
      width: 140,
      render: (_: unknown, m: JudgeModel) => (
        <DashTableActions>
          <DashTableLink onClick={() => jm.openEdit(m)}>编辑</DashTableLink>
          <Popconfirm title="确认删除该判分模型？" onConfirm={() => jm.deleteModel(m.id)}>
            <DashTableDangerLink>删除</DashTableDangerLink>
          </Popconfirm>
        </DashTableActions>
      ),
    },
  ];

  return (
    <DashboardPageShell
      title="判分模型（LLM-as-Judge）"
      sub="在此一次配好打分模型的连接信息与 Judge Prompt（含 API Key，仅写入、不回显），发起评测时直接下拉选用。"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={jm.openCreate}>
          新增判分模型
        </Button>
      }
    >
      <div className="dash-table-card">
        {jm.loadError ? (
          <AsyncLoadError message={jm.loadError} onRetry={jm.reload} />
        ) : (
          <Table
            className="dash-table"
            rowKey="id"
            loading={jm.loading}
            columns={columns}
            dataSource={jm.models}
            pagination={false}
          />
        )}
      </div>

      <JudgeModelEditModal
        open={jm.open}
        editId={jm.editId}
        saving={jm.saving}
        optimizing={jm.optimizing}
        form={jm.form}
        onCancel={() => jm.setOpen(false)}
        onSubmit={jm.submit}
        onOptimizePrompt={jm.optimizePrompt}
      />
    </DashboardPageShell>
  );
}
