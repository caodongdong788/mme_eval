import {
  Alert,
  Button,
  Drawer,
  Form,
  Input,
  Modal,
  Popconfirm,
  Segmented,
  Space,
  Table,
  Tag,
  Upload,
} from "antd";
import {
  DownloadOutlined,
  InboxOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { api } from "../api/index";
import { AsyncLoadError } from "../components/AsyncLoadError";
import { DashTableActions, DashTableDangerLink, DashTableLink } from "../components/DashTableActions";
import { DashboardPageShell } from "../components/DashboardPageShell";
import { createBenchmarkCaseColumns } from "../components/BenchmarkCaseColumns";
import { OnlineCasePreview } from "../components/OnlineCasePreview";
import { useBenchmarksPage } from "../hooks/useBenchmarksPage";

function benchmarkSourceLabel(source: string) {
  if (source === "builtin") return "内置";
  if (source === "online") return "线上";
  return "线下";
}

function benchmarkSourceColor(source: string) {
  if (source === "builtin") return "blue";
  if (source === "online") return "purple";
  return "green";
}

export default function BenchmarksPage() {
  const bm = useBenchmarksPage();
  const isOnlineCase = bm.casesBenchmark?.source === "online";

  const columns = [
    { title: "ID", dataIndex: "id", width: 60 },
    { title: "名称", dataIndex: "name" },
    {
      title: "来源",
      dataIndex: "source",
      width: 90,
      render: (s: string) =>
        <Tag color={benchmarkSourceColor(s)}>{benchmarkSourceLabel(s)}</Tag>,
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

  const caseColumns = createBenchmarkCaseColumns({
    isBuiltin: bm.casesBenchmark?.source === "builtin",
    onOpenCase: bm.openCaseYaml,
    onDeleteCase: bm.deleteCase,
  });

  return (
    <DashboardPageShell
      title="Benchmark 库"
      sub="管理内置与上传的评测用例集"
      extra={
        <Space>
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
        title={bm.replaceId != null ? `覆盖 benchmark #${bm.replaceId}` : "上传 benchmark"}
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
          <Form.Item
            name="default_evaluation_mode"
            label="默认对话模式"
            initialValue="single_turn"
            extra="作为发起评测时的默认值，仍可在发起页手动切换。动态多轮 Case 最多 3 轮；固定脚本式多轮最多 20 轮。"
          >
            <Segmented
              options={[
                { label: "单轮对话", value: "single_turn" },
                { label: "多轮对话", value: "multi_turn" },
              ]}
            />
          </Form.Item>
          <Form.Item name="source" label="来源" initialValue="offline">
            <Segmented
              onChange={() => {
                bm.setFileList([]);
                bm.form.setFieldValue("source_url", "");
              }}
              options={[
                { label: "线下", value: "offline" },
                { label: "线上", value: "online" },
              ]}
            />
          </Form.Item>
          {bm.sourceMode === "online" ? (
            <Form.Item
              name="source_url"
              label="飞书 URL（Base / Sheet / Wiki）"
              rules={[{ required: true, message: "请粘贴飞书 Base / Sheet / Wiki 链接" }]}
              extra="线上 benchmark 通过飞书表格导入，完整保留多轮对话；不支持文件上传。"
            >
              <Input placeholder="粘贴 https://*.feishu.cn/base、/sheets 或 /wiki 链接" />
            </Form.Item>
          ) : (
            <Form.Item
              label="用例文件 (.yaml / .zip)"
              extra="纯文本用例上传 YAML；含图片请上传 ZIP（根目录 cases.yaml，图片放 images/，在 turn.images 引用相对路径）。"
            >
              <Upload.Dragger
                accept=".yaml,.yml,.zip"
                maxCount={1}
                fileList={bm.fileList}
                beforeUpload={() => false}
                onChange={({ fileList }) => bm.setFileList(fileList)}
              >
                <p className="ant-upload-drag-icon">
                  <InboxOutlined />
                </p>
                <p>点击或拖拽 YAML / ZIP benchmark 包到此处</p>
              </Upload.Dragger>
            </Form.Item>
          )}
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
        {bm.casesError ? (
          <AsyncLoadError
            message={bm.casesError}
            onRetry={() => bm.casesBenchmark && bm.viewCases(bm.casesBenchmark)}
          />
        ) : null}
        <Table
          className="dash-table"
          rowKey="sample_id"
          size="small"
          loading={bm.casesLoading}
          columns={caseColumns}
          dataSource={bm.cases}
          pagination={{ pageSize: 20 }}
        />
      </Drawer>

      <Drawer
        title={`${isOnlineCase ? "线上对话" : "用例 YAML"} · ${bm.caseYamlMeta?.caseId ?? ""}`}
        width={760}
        open={bm.caseYamlOpen}
        onClose={() => bm.setCaseYamlOpen(false)}
        extra={
          isOnlineCase ? (
            <Button onClick={() => bm.setCaseYamlOpen(false)}>关闭</Button>
          ) : (
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
          )
        }
      >
        {bm.casesBenchmark?.source === "builtin" ? (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
            message="内置用例直接写回仓库 cases/；Docker 重建镜像后修改会丢失，生产环境请下载后作为上传集维护。"
          />
        ) : null}
        {isOnlineCase ? (
          <OnlineCasePreview yamlText={bm.caseYamlText} />
        ) : (
          <Input.TextArea
            value={bm.caseYamlText}
            onChange={(e) => bm.setCaseYamlText(e.target.value)}
            placeholder={bm.caseYamlLoading ? "加载 YAML 中…" : ""}
            autoSize={{ minRows: 20, maxRows: 42 }}
            style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}
          />
        )}
      </Drawer>
    </DashboardPageShell>
  );
}
