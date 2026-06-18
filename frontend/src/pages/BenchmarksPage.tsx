import {
  Alert,
  Button,
  Drawer,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
} from "antd";
import {
  DownloadOutlined,
  FileTextOutlined,
  InboxOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { api } from "../api/index";
import { AsyncLoadError } from "../components/AsyncLoadError";
import { DashTableActions, DashTableDangerLink, DashTableLink } from "../components/DashTableActions";
import { DashboardPageShell } from "../components/DashboardPageShell";
import { useBenchmarksPage } from "../hooks/useBenchmarksPage";
import { PROFILE_LABEL } from "../labels";
import type { CaseBrief } from "../api/types";

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
        <DashTableActions>
          <DashTableLink onClick={() => bm.viewCases(b)}>查看用例</DashTableLink>
          <DashTableLink onClick={() => bm.openEdit(b)}>编辑</DashTableLink>
          <DashTableLink href={api.downloadBenchmarkUrl(b.id)} download>
            <DownloadOutlined /> 下载
          </DashTableLink>
          <DashTableLink onClick={() => bm.openReplace(b)}>覆盖</DashTableLink>
          <Popconfirm title="确认删除该 benchmark?" onConfirm={() => bm.deleteBenchmark(b.id)}>
            <DashTableDangerLink>删除</DashTableDangerLink>
          </Popconfirm>
        </DashTableActions>
      ),
    },
  ];

  const caseColumns = [
    {
      title: "子场景",
      dataIndex: "sub_scenario",
      render: (text: string, row: CaseBrief) => (
        <DashTableLink onClick={() => bm.openCaseYaml(row)}>{text || row.sample_id}</DashTableLink>
      ),
    },
    { title: "场景", dataIndex: "scenario" },
    { title: "Level", dataIndex: "level", width: 80 },
    {
      title: "Profile",
      dataIndex: "score_profile",
      width: 120,
      render: (p: string) => PROFILE_LABEL[p] || p,
    },
  ];

  return (
    <DashboardPageShell
      title="Benchmark 库"
      sub="管理内置与上传的评测用例集"
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
      <div className="dash-table-card">
        {bm.loadError ? (
          <AsyncLoadError message={bm.loadError} onRetry={bm.reload} />
        ) : (
          <Table
            className="dash-table"
            rowKey="id"
            loading={bm.loading}
            columns={columns}
            dataSource={bm.uploaded}
            pagination={{ showTotal: (t) => `共 ${t} 条` }}
          />
        )}
      </div>

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
          className="dash-table"
          rowKey="sample_id"
          size="small"
          columns={caseColumns}
          dataSource={bm.cases}
          pagination={{ pageSize: 20 }}
        />
      </Drawer>

      <Drawer
        title={`用例 YAML · ${bm.caseYamlMeta?.subScenario ?? ""}`}
        width={760}
        open={bm.caseYamlOpen}
        onClose={() => bm.setCaseYamlOpen(false)}
        extra={
          <Space>
            <Button onClick={() => bm.setCaseYamlOpen(false)}>取消</Button>
            <Button
              type="primary"
              loading={bm.caseYamlSaving}
              disabled={bm.caseYamlLoading || !bm.caseYamlText}
              onClick={bm.saveCaseYaml}
            >
              保存
            </Button>
          </Space>
        }
      >
        {bm.caseYamlMeta?.caseFile ? (
          <Typography.Text type="secondary" style={{ display: "block", marginBottom: 8, fontSize: 12 }}>
            源文件：{bm.caseYamlMeta.caseFile}
          </Typography.Text>
        ) : null}
        {bm.casesBenchmark?.source === "builtin" ? (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
            message="内置用例直接写回仓库 cases/；Docker 重建镜像后修改会丢失，生产环境请下载后作为上传集维护。"
          />
        ) : null}
        <Input.TextArea
          value={bm.caseYamlText}
          onChange={(e) => bm.setCaseYamlText(e.target.value)}
          placeholder={bm.caseYamlLoading ? "加载 YAML 中…" : ""}
          autoSize={{ minRows: 20, maxRows: 42 }}
          style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}
        />
      </Drawer>
    </DashboardPageShell>
  );
}
