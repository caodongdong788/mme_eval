import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { PlusOutlined, ReloadOutlined, SyncOutlined } from "@ant-design/icons";
import { api, OpenApiAccessKey, OpenApiPermission } from "../api";
import { formatApiError } from "../utils/apiError";

const PERMISSIONS: Array<{ value: OpenApiPermission; label: string; description: string }> = [
  { value: "benchmarks:read", label: "读取评测用例集", description: "查询可用 Benchmark" },
  { value: "judge_models:read", label: "读取判分模型", description: "查询可用判分模型" },
  { value: "evaluations:create", label: "创建评测任务", description: "通过 API 发起评测" },
  { value: "evaluations:read", label: "查询任务状态", description: "查看评测进度和结果" },
];

const permissionLabels = Object.fromEntries(PERMISSIONS.map((item) => [item.value, item.label]));

export function OpenApiKeysPanel() {
  const [keys, setKeys] = useState<OpenApiAccessKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<OpenApiAccessKey>();
  const [editorOpen, setEditorOpen] = useState(false);
  const [issuedKey, setIssuedKey] = useState<OpenApiAccessKey>();
  const [form] = Form.useForm<{ name: string; permissions: OpenApiPermission[] }>();

  const reload = async () => {
    setLoading(true);
    try {
      setKeys(await api.listOpenApiKeys());
    } catch (error) {
      message.error(formatApiError(error, "读取 OpenAPI Key 失败"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
  }, []);

  const openCreate = () => {
    setEditing(undefined);
    form.setFieldsValue({ name: "", permissions: PERMISSIONS.map((item) => item.value) });
    setEditorOpen(true);
  };

  const openEdit = (key: OpenApiAccessKey) => {
    setEditing(key);
    form.setFieldsValue({ name: key.name, permissions: key.permissions });
    setEditorOpen(true);
  };

  const submit = async () => {
    let values: { name: string; permissions: OpenApiPermission[] };
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        await api.updateOpenApiKey(editing.id, values);
        message.success("权限已更新");
      } else {
        const key = await api.createOpenApiKey(values);
        setIssuedKey(key);
        message.success("OpenAPI Key 已生成");
      }
      setEditorOpen(false);
      await reload();
    } catch (error) {
      message.error(formatApiError(error, "保存失败"));
    } finally {
      setSaving(false);
    }
  };

  const rotate = async (key: OpenApiAccessKey) => {
    try {
      const next = await api.rotateOpenApiKey(key.id);
      setIssuedKey(next);
      await reload();
      message.success("Key 已轮换，旧 Key 已失效");
    } catch (error) {
      message.error(formatApiError(error, "轮换失败"));
    }
  };

  const remove = async (key: OpenApiAccessKey) => {
    try {
      await api.deleteOpenApiKey(key.id);
      await reload();
      message.success("OpenAPI Key 已删除");
    } catch (error) {
      message.error(formatApiError(error, "删除失败"));
    }
  };

  const columns = [
    { title: "名称", dataIndex: "name", width: 180 },
    {
      title: "API Key",
      dataIndex: "key_prefix",
      width: 210,
      render: (_: string, key: OpenApiAccessKey) => (
        <Typography.Text className="mono" copyable={{ text: key.api_key, tooltips: ["复制完整 Key", "已复制"] }}>
          {key.key_prefix}
        </Typography.Text>
      ),
    },
    {
      title: "权限",
      dataIndex: "permissions",
      render: (permissions: OpenApiPermission[]) => (
        <Space size={[4, 4]} wrap>
          {permissions.map((permission) => <Tag color="purple" key={permission}>{permissionLabels[permission]}</Tag>)}
        </Space>
      ),
    },
    { title: "创建人", dataIndex: "created_by", width: 110, render: (value: string) => value || "—" },
    {
      title: "最近使用",
      dataIndex: "last_used_at",
      width: 170,
      render: (value: string) => value ? new Date(value).toLocaleString() : "尚未使用",
    },
    {
      title: "操作",
      width: 210,
      render: (_: unknown, key: OpenApiAccessKey) => (
        <Space size={12}>
          <Typography.Link onClick={() => openEdit(key)}>编辑权限</Typography.Link>
          <Popconfirm title="确认轮换 Key？旧 Key 会立刻失效。" onConfirm={() => rotate(key)}>
            <Typography.Link><SyncOutlined /> 轮换</Typography.Link>
          </Popconfirm>
          <Popconfirm title="确认删除这把 Key？删除后将无法再调用 OpenAPI。" onConfirm={() => remove(key)}>
            <Typography.Link type="danger">删除</Typography.Link>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="dash-table-card" style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, marginBottom: 18 }}>
        <div>
          <Typography.Title level={4} style={{ margin: 0 }}>Open API 访问密钥</Typography.Title>
          <Typography.Text type="secondary">每把 Key 可独立配置权限；点击 Key 前缀即可复制完整值。</Typography.Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={reload}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建 API Key</Button>
        </Space>
      </div>
      <Alert
        showIcon
        type={keys.length ? "success" : "info"}
        message={keys.length ? `当前已启用 ${keys.length} 把 OpenAPI Key` : "尚未创建 OpenAPI Key"}
        description="Key 可用于请求头 X-MME-API-Key；请按集成方实际需要勾选最小权限。"
        style={{ marginBottom: 16 }}
      />
      <Table rowKey="id" loading={loading} columns={columns} dataSource={keys} pagination={false} />

      <Modal
        open={editorOpen}
        title={editing ? `编辑权限 · ${editing.name}` : "新建 OpenAPI Key"}
        okText={editing ? "保存权限" : "生成 Key"}
        confirmLoading={saving}
        onCancel={() => setEditorOpen(false)}
        onOk={submit}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Key 名称" rules={[{ required: true, whitespace: true, message: "请输入 Key 名称" }]}>
            <Input placeholder="例如：CI 回归、数据平台" maxLength={120} />
          </Form.Item>
          <Form.Item name="permissions" label="接口权限" rules={[{ required: true, type: "array", min: 1, message: "请至少选择一项权限" }]}>
            <Checkbox.Group style={{ display: "grid", gap: 12 }}>
              {PERMISSIONS.map((permission) => (
                <Checkbox value={permission.value} key={permission.value}>
                  <Typography.Text strong>{permission.label}</Typography.Text>
                  <Typography.Text type="secondary"> · {permission.description}</Typography.Text>
                </Checkbox>
              ))}
            </Checkbox.Group>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={Boolean(issuedKey)}
        title="API Key 已生成"
        okText="完成"
        cancelButtonProps={{ style: { display: "none" } }}
        onOk={() => setIssuedKey(undefined)}
        onCancel={() => setIssuedKey(undefined)}
      >
        <Alert showIcon type="warning" message="请复制并妥善保管此 Key" style={{ marginBottom: 16 }} />
        {issuedKey && (
          <Typography.Paragraph copyable={{ text: issuedKey.api_key, tooltips: ["复制完整 Key", "已复制"] }} className="mono">
            {issuedKey.api_key}
          </Typography.Paragraph>
        )}
      </Modal>
    </div>
  );
}
