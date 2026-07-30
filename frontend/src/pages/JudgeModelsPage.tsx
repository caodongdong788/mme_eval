import { useState } from "react";
import { Alert, Button, Popconfirm, Table, Tabs, Tag, Typography } from "antd";
import { PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import { EvaluationAccount, JudgeModel } from "../api/index";
import { AsyncLoadError } from "../components/AsyncLoadError";
import {
  DashTableActions,
  DashTableDangerLink,
  DashTableLink,
} from "../components/DashTableActions";
import { DashboardPageShell } from "../components/DashboardPageShell";
import { JudgeModelEditModal } from "../components/JudgeModelEditModal";
import { useEvaluationAccounts } from "../hooks/useEvaluationAccounts";
import { useJudgeModelsPage } from "../hooks/useJudgeModelsPage";

export default function JudgeModelsPage() {
  const jm = useJudgeModelsPage();
  const [activeTab, setActiveTab] = useState("models");
  const accounts = useEvaluationAccounts();
  const accountRows = accounts.data?.accounts ?? [];
  const statelessCount = accountRows.filter(
    (account) => account.pool === "stateless"
  ).length;
  const statefulCount = accountRows.filter(
    (account) => account.pool === "stateful"
  ).length;

  const modelColumns = [
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
        u ? (
          <span className="mono">{u}</span>
        ) : (
          <Typography.Text type="secondary">默认</Typography.Text>
        ),
    },
    {
      title: "对比并发",
      dataIndex: "pairwise_concurrency",
      width: 90,
      render: (n: number) => <span className="mono">{n ?? 4}</span>,
    },
    {
      title: "创建人",
      dataIndex: "created_by",
      width: 110,
      render: (v: string | null) =>
        v || <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: "操作",
      width: 140,
      render: (_: unknown, m: JudgeModel) => (
        <DashTableActions>
          <DashTableLink onClick={() => jm.openEdit(m)}>编辑</DashTableLink>
          <Popconfirm
            title="确认删除该判分模型？"
            onConfirm={() => jm.deleteModel(m.id)}
          >
            <DashTableDangerLink>删除</DashTableDangerLink>
          </Popconfirm>
        </DashTableActions>
      ),
    },
  ];
  const accountColumns = [
    {
      title: "账号池",
      dataIndex: "pool_label",
      width: 150,
      render: (label: string, account: EvaluationAccount) => (
        <Tag color={account.pool === "stateful" ? "purple" : "blue"}>
          {label}
        </Tag>
      ),
    },
    {
      title: "手机号",
      dataIndex: "phone",
      width: 190,
      render: (phone: string) => <span className="mono">{phone}</span>,
    },
    {
      title: "固定验证码",
      dataIndex: "verification_code",
      width: 130,
      render: (code: string) => <span className="mono">{code}</span>,
    },
    {
      title: "用户 ID",
      dataIndex: "user_id",
      width: 390,
      render: (id: string) => <span className="mono">{id}</span>,
    },
    { title: "适用范围", dataIndex: "usage" },
  ];

  return (
    <DashboardPageShell
      title="参数配置"
      sub="管理评测使用的判分模型，以及 cx-agent 专用测试账号池。"
      extra={
        activeTab === "models" ? (
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={jm.openCreate}
          >
            新增判分模型
          </Button>
        ) : (
          <Button
            icon={<ReloadOutlined />}
            loading={accounts.loading}
            onClick={accounts.reload}
          >
            刷新账号
          </Button>
        )
      }
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: "models",
            label: "模型配置",
            children: (
              <div className="dash-table-card">
                {jm.loadError ? (
                  <AsyncLoadError message={jm.loadError} onRetry={jm.reload} />
                ) : (
                  <Table
                    className="dash-table"
                    rowKey="id"
                    loading={jm.loading}
                    columns={modelColumns}
                    dataSource={jm.models}
                    pagination={false}
                  />
                )}
              </div>
            ),
          },
          {
            key: "accounts",
            label: accountRows.length
              ? `账号配置（${accountRows.length}）`
              : "账号配置",
            children: (
              <div className="dash-table-card">
                <Alert
                  showIcon
                  type="info"
                  message={
                    accountRows.length
                      ? `当前共 ${accountRows.length} 个账号：普通评测 ${statelessCount} 个，长期记忆评测 ${statefulCount} 个。账号由系统自动领取、清空，并在 Case 完成后释放。`
                      : "账号由评测系统自动领取、清空，并在 Case 完成后释放；普通评测与长期记忆评测使用相互隔离的账号池。"
                  }
                  style={{ margin: "16px 16px 0" }}
                />
                {accounts.error ? (
                  <AsyncLoadError
                    message={String(accounts.error)}
                    onRetry={accounts.reload}
                  />
                ) : (
                  <Table
                    className="dash-table"
                    rowKey="user_id"
                    loading={accounts.loading}
                    columns={accountColumns}
                    dataSource={accountRows}
                    pagination={false}
                    style={{ marginTop: 16 }}
                  />
                )}
              </div>
            ),
          },
        ]}
      />
      <JudgeModelEditModal
        open={jm.open}
        editId={jm.editId}
        saving={jm.saving}
        form={jm.form}
        onCancel={() => jm.setOpen(false)}
        onSubmit={jm.submit}
      />
    </DashboardPageShell>
  );
}
