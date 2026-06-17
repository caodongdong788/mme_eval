import {
  Button,
  Divider,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Typography,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { JudgeModel } from "../api/index";
import { AsyncLoadError } from "../components/AsyncLoadError";
import { DashTableActions, DashTableDangerLink, DashTableLink } from "../components/DashTableActions";
import { DashboardPageShell } from "../components/DashboardPageShell";
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
      sub="在此一次配好打分模型的连接信息（含 API Key，仅写入、不回显），发起评测时直接下拉选用，免手填。"
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

      <Modal
        title={jm.editId != null ? "编辑判分模型" : "新增判分模型"}
        open={jm.open}
        onOk={jm.submit}
        confirmLoading={jm.saving}
        onCancel={() => jm.setOpen(false)}
        okText="保存"
        cancelText="取消"
        width={560}
      >
        <Form form={jm.form} layout="vertical">
          <Form.Item name="name" label="配置名称" rules={[{ required: true, message: "请输入名称" }]}>
            <Input placeholder="如：强判官-gpt5.1" />
          </Form.Item>
          <Space style={{ display: "flex" }} align="start">
            <Form.Item name="provider" label="Provider" style={{ flex: 1 }}>
              <Select
                options={[
                  { value: "openai", label: "openai" },
                  { value: "azure", label: "azure" },
                ]}
              />
            </Form.Item>
            <Form.Item
              name="model"
              label="模型"
              style={{ flex: 2 }}
              rules={[{ required: true, message: "请输入模型名" }]}
            >
              <Input placeholder="如 gpt-5.1 / gpt-4o" />
            </Form.Item>
          </Space>
          <Form.Item name="base_url" label="Base URL（可选）">
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          <Space style={{ display: "flex" }} align="start">
            <Form.Item name="api_version" label="API Version（azure，可选）" style={{ flex: 1 }}>
              <Input placeholder="2024-02-01" />
            </Form.Item>
            <Form.Item name="temperature" label="Temperature（可选）" style={{ flex: 1 }}>
              <InputNumber min={0} max={2} step={0.1} style={{ width: "100%" }} />
            </Form.Item>
          </Space>
          <Form.Item
            name="api_key"
            label={jm.editId != null ? "API Key（留空=保持不变）" : "API Key"}
            extra="仅写入后端、不回显；发起评测时由服务端注入运行期。"
          >
            <Input.Password placeholder={jm.editId != null ? "留空则不修改" : "sk-..."} autoComplete="off" />
          </Form.Item>

          <Divider orientation="left" plain style={{ marginTop: 4 }}>
            <Typography.Text type="secondary">Pairwise 对比</Typography.Text>
          </Divider>
          <Form.Item
            name="pairwise_concurrency"
            label="对比并发（题间）"
            rules={[{ required: true, message: "请输入并发度" }]}
            extra="仅作用于 Pairwise 对比：同时比较几道用例（题内两次裁判默认并行）。不影响主评测端并发。"
          >
            <InputNumber min={1} max={32} step={1} style={{ width: "100%" }} placeholder="默认 4" />
          </Form.Item>
        </Form>
      </Modal>
    </DashboardPageShell>
  );
}
