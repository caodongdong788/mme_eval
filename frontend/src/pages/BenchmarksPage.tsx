import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Drawer,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
  Upload,
  message,
} from "antd";
import {
  DownloadOutlined,
  FileTextOutlined,
  InboxOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import type { UploadFile } from "antd";
import { api, Benchmark, CaseBrief } from "../api";
import { formatApiError } from "../utils/apiError";

export default function BenchmarksPage() {
  const [list, setList] = useState<Benchmark[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  // null = 新建上传；数字 = 覆盖该 benchmark
  const [replaceId, setReplaceId] = useState<number | null>(null);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [form] = Form.useForm();
  const [casesOpen, setCasesOpen] = useState(false);
  const [cases, setCases] = useState<CaseBrief[]>([]);
  const [casesTitle, setCasesTitle] = useState("");
  const [editForm] = Form.useForm();
  const [editOpen, setEditOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);

  const builtin = list.find((b) => b.source === "builtin");
  const uploaded = list.filter((b) => b.source !== "builtin");

  const reload = async () => {
    setLoading(true);
    try {
      setList(await api.listBenchmarks());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, []);

  const openCreate = () => {
    setReplaceId(null);
    setFileList([]);
    form.resetFields();
    setModalOpen(true);
  };

  const openReplace = (b: Benchmark) => {
    setReplaceId(b.id);
    setFileList([]);
    form.resetFields();
    setModalOpen(true);
  };

  const submit = async () => {
    const file = fileList[0]?.originFileObj;
    if (!file) {
      message.error("请选择一个 YAML 用例文件");
      return;
    }
    const fd = new FormData();
    fd.append("file", file);
    try {
      if (replaceId != null) {
        await api.replaceBenchmark(replaceId, fd);
        message.success("覆盖成功");
      } else {
        const values = await form.validateFields();
        fd.append("name", values.name);
        fd.append("description", values.description || "");
        await api.uploadBenchmark(fd);
        message.success("上传成功");
      }
      setModalOpen(false);
      setFileList([]);
      form.resetFields();
      reload();
    } catch (e: any) {
      message.error(formatApiError(e, "操作失败"));
    }
  };

  const viewCases = async (b: Benchmark) => {
    setCasesTitle(`${b.name}（${b.case_count} 条用例）`);
    setCasesOpen(true);
    setCases(await api.getBenchmarkCases(b.id));
  };

  const openEdit = (b: Benchmark) => {
    setEditId(b.id);
    editForm.setFieldsValue({ name: b.name, description: b.description });
    setEditOpen(true);
  };

  const submitEdit = async () => {
    try {
      const v = await editForm.validateFields();
      await api.updateBenchmark(editId!, {
        name: v.name,
        description: v.description || "",
      });
      message.success("已保存");
      setEditOpen(false);
      reload();
    } catch (e: any) {
      if (e?.errorFields) return; // 表单校验失败
      message.error(formatApiError(e, "保存失败"));
    }
  };

  const columns = [
    { title: "ID", dataIndex: "id", width: 60 },
    { title: "名称", dataIndex: "name" },
    {
      title: "来源",
      dataIndex: "source",
      width: 90,
      render: (s: string) =>
        s === "builtin" ? <Tag color="blue">内置</Tag> : <Tag color="green">上传</Tag>,
    },
    { title: "用例数", dataIndex: "case_count", width: 80 },
    {
      title: "上传人",
      dataIndex: "created_by",
      width: 110,
      render: (v: string | null, b: Benchmark) =>
        b.source === "builtin" ? (
          <Tag>内置</Tag>
        ) : (
          <span style={{ color: v ? undefined : "var(--muted)" }}>{v || "未知"}</span>
        ),
    },
    {
      title: "Level",
      dataIndex: "levels",
      render: (levels: string[]) =>
        (levels || []).map((l) => (
          <Tag key={l} color="geekblue">
            {l}
          </Tag>
        )),
    },
    {
      title: "操作",
      width: 280,
      render: (_: any, b: Benchmark) => (
        <Space>
          <a onClick={() => viewCases(b)}>查看用例</a>
          <a onClick={() => openEdit(b)}>编辑</a>
          <a href={api.downloadBenchmarkUrl(b.id)} download>
            <DownloadOutlined /> 下载
          </a>
          <a onClick={() => openReplace(b)}>覆盖</a>
          <Popconfirm
            title="确认删除该 benchmark?"
            onConfirm={async () => {
              await api.deleteBenchmark(b.id);
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

  const caseColumns = [
    { title: "子场景", dataIndex: "sub_scenario" },
    { title: "场景", dataIndex: "scenario" },
    { title: "Level", dataIndex: "level", width: 80 },
    { title: "Profile", dataIndex: "score_profile", width: 110 },
  ];

  return (
    <Card
      title="Benchmark 库"
      extra={
        <Space>
          <Button
            icon={<FileTextOutlined />}
            href={builtin ? api.downloadBenchmarkUrl(builtin.id) : undefined}
            download
            disabled={!builtin}
            title="下载内置乳腺癌专科用例模板（YAML，可改后作为新 benchmark 上传）"
          >
            用例模板{builtin ? `（${builtin.case_count}）` : ""} <DownloadOutlined />
          </Button>
          <Button type="primary" icon={<UploadOutlined />} onClick={openCreate}>
            上传 benchmark
          </Button>
        </Space>
      }
    >
      <Table rowKey="id" loading={loading} columns={columns} dataSource={uploaded} />

      <Modal
        title={replaceId != null ? `覆盖 benchmark #${replaceId}` : "上传 benchmark（YAML 用例集，格式同 cases/）"}
        open={modalOpen}
        onOk={submit}
        onCancel={() => setModalOpen(false)}
        okText={replaceId != null ? "覆盖" : "上传"}
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          {replaceId == null && (
            <>
              <Form.Item name="name" label="名称" rules={[{ required: true, message: "请输入名称" }]}>
                <Input placeholder="如：乳腺癌补充集" />
              </Form.Item>
              <Form.Item name="description" label="描述">
                <Input.TextArea rows={2} />
              </Form.Item>
            </>
          )}
          <Form.Item label="用例文件 (.yaml)">
            <Upload.Dragger
              accept=".yaml,.yml"
              maxCount={1}
              fileList={fileList}
              beforeUpload={() => false}
              onChange={({ fileList }) => setFileList(fileList)}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p>点击或拖拽 YAML 文件到此处</p>
            </Upload.Dragger>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="编辑 benchmark"
        open={editOpen}
        onOk={submitEdit}
        onCancel={() => setEditOpen(false)}
        okText="保存"
        cancelText="取消"
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: "请输入名称" }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer title={casesTitle} width={720} open={casesOpen} onClose={() => setCasesOpen(false)}>
        <Table
          rowKey="sample_id"
          size="small"
          columns={caseColumns}
          dataSource={cases}
          pagination={{ pageSize: 20 }}
        />
      </Drawer>
    </Card>
  );
}
