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
} from "antd";
import {
  DownloadOutlined,
  FileTextOutlined,
  InboxOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { api } from "../api/index";
import { useBenchmarksPage } from "../hooks/useBenchmarksPage";

export default function BenchmarksPage() {
  const bm = useBenchmarksPage();

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
      render: (v: string | null, b: { source: string }) =>
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
      render: (_: unknown, b: (typeof bm.uploaded)[0]) => (
        <Space>
          <a onClick={() => bm.viewCases(b)}>查看用例</a>
          <a onClick={() => bm.openEdit(b)}>编辑</a>
          <a href={api.downloadBenchmarkUrl(b.id)} download>
            <DownloadOutlined /> 下载
          </a>
          <a onClick={() => bm.openReplace(b)}>覆盖</a>
          <Popconfirm title="确认删除该 benchmark?" onConfirm={() => bm.deleteBenchmark(b.id)}>
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
            href={bm.builtin ? api.downloadBenchmarkUrl(bm.builtin.id) : undefined}
            download
            disabled={!bm.builtin}
            title="下载内置乳腺癌专科用例模板（YAML，可改后作为新 benchmark 上传）"
          >
            用例模板{bm.builtin ? `（${bm.builtin.case_count}）` : ""} <DownloadOutlined />
          </Button>
          <Button type="primary" icon={<UploadOutlined />} onClick={bm.openCreate}>
            上传 benchmark
          </Button>
        </Space>
      }
    >
      <Table rowKey="id" loading={bm.loading} columns={columns} dataSource={bm.uploaded} />

      <Modal
        title={
          bm.replaceId != null
            ? `覆盖 benchmark #${bm.replaceId}`
            : "上传 benchmark（YAML 用例集，格式同 cases/）"
        }
        open={bm.modalOpen}
        onOk={bm.submit}
        onCancel={() => bm.setModalOpen(false)}
        okText={bm.replaceId != null ? "覆盖" : "上传"}
        cancelText="取消"
      >
        <Form form={bm.form} layout="vertical">
          {bm.replaceId == null && (
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
              fileList={bm.fileList}
              beforeUpload={() => false}
              onChange={({ fileList }) => bm.setFileList(fileList)}
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
        open={bm.editOpen}
        onOk={bm.submitEdit}
        onCancel={() => bm.setEditOpen(false)}
        okText="保存"
        cancelText="取消"
      >
        <Form form={bm.editForm} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: "请输入名称" }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer title={bm.casesTitle} width={720} open={bm.casesOpen} onClose={() => bm.setCasesOpen(false)}>
        <Table
          rowKey="sample_id"
          size="small"
          columns={caseColumns}
          dataSource={bm.cases}
          pagination={{ pageSize: 20 }}
        />
      </Drawer>
    </Card>
  );
}
