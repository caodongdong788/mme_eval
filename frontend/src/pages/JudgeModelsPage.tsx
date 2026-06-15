import { useEffect, useState } from "react";
import {
  Button,
  Card,
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
  message,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { api, JudgeModel } from "../api";
import { formatApiError } from "../utils/apiError";

export default function JudgeModelsPage() {
  const [list, setList] = useState<JudgeModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const reload = async () => {
    setLoading(true);
    try {
      setList(await api.listJudgeModels());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, []);

  const openCreate = () => {
    setEditId(null);
    form.resetFields();
    form.setFieldsValue({ provider: "openai", pairwise_concurrency: 4 });
    setOpen(true);
  };

  const openEdit = (m: JudgeModel) => {
    setEditId(m.id);
    form.resetFields();
    form.setFieldsValue({
      name: m.name,
      provider: m.provider || "openai",
      model: m.model,
      base_url: m.base_url,
      api_version: m.api_version,
      temperature: m.temperature ?? undefined,
      pairwise_concurrency: m.pairwise_concurrency ?? 4,
      api_key: "", // 留空=保持原 Key 不变
    });
    setOpen(true);
  };

  const submit = async () => {
    let v: any;
    try {
      v = await form.validateFields();
    } catch {
      return; // 表单校验失败
    }
    const payload = {
      name: v.name?.trim(),
      provider: v.provider || "openai",
      model: v.model?.trim(),
      base_url: v.base_url || undefined,
      api_version: v.api_version || undefined,
      temperature: v.temperature ?? undefined,
      pairwise_concurrency: v.pairwise_concurrency ?? undefined,
      api_key: v.api_key ? v.api_key : undefined, // 空串=不变（编辑）/不设（新建）
    };
    setSaving(true);
    try {
      if (editId != null) {
        await api.updateJudgeModel(editId, payload);
        message.success("已保存");
      } else {
        await api.createJudgeModel(payload);
        message.success("已创建");
      }
      setOpen(false);
      reload();
    } catch (e: any) {
      message.error(formatApiError(e, "保存失败"));
    } finally {
      setSaving(false);
    }
  };

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
      render: (_: any, m: JudgeModel) => (
        <Space>
          <a onClick={() => openEdit(m)}>编辑</a>
          <Popconfirm
            title="确认删除该判分模型？"
            onConfirm={async () => {
              await api.deleteJudgeModel(m.id);
              message.success("已删除");
              reload();
            }}
          >
            <a style={{ color: "var(--fail)" }}>删除</a>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="判分模型（LLM-as-Judge）"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增判分模型
        </Button>
      }
    >
      <Typography.Paragraph type="secondary" style={{ marginTop: -4 }}>
        在此一次配好打分模型的连接信息（含 API Key，仅写入、不回显），发起评测时直接下拉选用，免手填。
      </Typography.Paragraph>
      <Table rowKey="id" loading={loading} columns={columns} dataSource={list} pagination={false} />

      <Modal
        title={editId != null ? "编辑判分模型" : "新增判分模型"}
        open={open}
        onOk={submit}
        confirmLoading={saving}
        onCancel={() => setOpen(false)}
        okText="保存"
        cancelText="取消"
        width={560}
      >
        <Form form={form} layout="vertical">
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
            label={editId != null ? "API Key（留空=保持不变）" : "API Key"}
            extra="仅写入后端、不回显；发起评测时由服务端注入运行期。"
          >
            <Input.Password placeholder={editId != null ? "留空则不修改" : "sk-..."} autoComplete="off" />
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
    </Card>
  );
}
