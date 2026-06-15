import { Button, Card, Popconfirm, Progress, Space, Table, Tag, Tooltip, Typography } from "antd";
import type { PairwiseComparison } from "../api/index";

const { Text } = Typography;

export function PairwiseHistoryTable({
  history,
  onView,
  onSaveNote,
  onDelete,
}: {
  history: PairwiseComparison[];
  onView: (id: number) => void;
  onSaveNote: (id: number, value: string) => void;
  onDelete: (id: number) => void;
}) {
  return (
    <Card title="历史对比">
      <Table<PairwiseComparison>
        rowKey="id"
        dataSource={history}
        size="small"
        pagination={{ pageSize: 10 }}
        columns={[
          { title: "ID", dataIndex: "id", width: 70 },
          {
            title: "A vs B",
            render: (_, r) => (
              <Tooltip
                title={`A=${r.run_a_name || "#" + r.run_a_id} · B=${
                  r.run_b_name || "#" + r.run_b_id
                }`}
              >
                <Text className="mono">
                  #{r.run_a_id} vs #{r.run_b_id}
                </Text>
              </Tooltip>
            ),
          },
          { title: "裁判", dataIndex: "judge_model" },
          {
            title: "描述",
            width: 240,
            render: (_, r) => (
              <Typography.Paragraph
                style={{ margin: 0, maxWidth: 240 }}
                type={r.note ? undefined : "secondary"}
                editable={{
                  text: r.note || "",
                  tooltip: "编辑备注",
                  autoSize: { minRows: 1, maxRows: 4 },
                  onChange: (v) => onSaveNote(r.id, v),
                }}
              >
                {r.note || "（点击编辑添加备注）"}
              </Typography.Paragraph>
            ),
          },
          {
            title: "状态",
            dataIndex: "status",
            width: 190,
            render: (s: string, r) => {
              if (s === "running") {
                const total = r.total_cases || 0;
                const done = r.done_cases || 0;
                const pct = total ? Math.round((done / total) * 100) : 0;
                return (
                  <Space direction="vertical" size={2} style={{ minWidth: 170, display: "flex" }}>
                    <Tag color="blue">{total ? "进行中" : "准备中"}</Tag>
                    <Tooltip title={`${done}/${total || "…"}`}>
                      <Progress percent={pct} size="small" status="active" />
                    </Tooltip>
                  </Space>
                );
              }
              const color = s === "done" ? "green" : s === "failed" ? "red" : "blue";
              const label = s === "done" ? "完成" : s === "failed" ? "失败" : "进行中";
              return <Tag color={color}>{label}</Tag>;
            },
          },
          {
            title: "结论",
            render: (_, r) => {
              if (r.status !== "done" || !r.summary?.overall_winner) return "—";
              const w = r.summary.overall_winner;
              if (w === "tie") return <Text>持平</Text>;
              const name = w === "B" ? r.run_b_name || "B" : r.run_a_name || "A";
              return <Text>{name} 更优</Text>;
            },
          },
          {
            title: "操作",
            width: 120,
            render: (_, r) => (
              <Space size={4}>
                <Button type="link" size="small" onClick={() => onView(r.id)}>
                  查看
                </Button>
                <Popconfirm
                  title="确认删除该对比？"
                  description="将连带删除其逐用例结论，不可恢复。"
                  okText="删除"
                  cancelText="取消"
                  okButtonProps={{ danger: true }}
                  onConfirm={() => onDelete(r.id)}
                >
                  <Button type="link" size="small" danger>
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
    </Card>
  );
}
