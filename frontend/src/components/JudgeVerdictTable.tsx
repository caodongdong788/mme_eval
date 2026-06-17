import { Space, Table, Tag, Typography } from "antd";
import { useJudgeVerdictLabels } from "../judgeVerdictLabels";
import { CaseVerdict } from "../utils/caseJudging";
import { DashPanel } from "./DashPanel";

const { Text } = Typography;

export interface JudgeVerdictTableProps {
  verdicts: CaseVerdict[];
  tagLabel: (tag: string) => string;
}

export function JudgeVerdictTable({ verdicts, tagLabel }: JudgeVerdictTableProps) {
  const judgeLabel = useJudgeVerdictLabels();
  const columns = [
    {
      title: "Judge",
      dataIndex: "name",
      width: 200,
      render: (name: string) => (
        <Space direction="vertical" size={0}>
          <Text>{judgeLabel(name)}</Text>
          <Text type="secondary" style={{ fontSize: 11 }} className="mono">
            {name}
          </Text>
        </Space>
      ),
    },
    {
      title: "结果",
      dataIndex: "passed",
      width: 80,
      render: (p: boolean) =>
        p ? (
          <span className="status-dot status-dot--pass">PASS</span>
        ) : (
          <span className="status-dot status-dot--fail">FAIL</span>
        ),
    },
    {
      title: "分数",
      width: 90,
      render: (_: unknown, v: CaseVerdict) => (v.max_score ? `${v.score}/${v.max_score}` : "-"),
    },
    { title: "原因", dataIndex: "reason" },
    {
      title: "失败标签",
      dataIndex: "failure_tags",
      render: (t: string[]) =>
        (t || []).map((x) => (
          <Tag key={x} color="red" bordered={false}>
            {tagLabel(x)}
          </Tag>
        )),
    },
    {
      title: "语义救回",
      dataIndex: "adjudicated",
      width: 90,
      render: (a: boolean) => (a ? <Tag color="blue">是</Tag> : ""),
    },
  ];

  return (
    <DashPanel title="Judge 判定" bodyClassName="dash-panel__body--flush">
      <Table
        className="dash-table"
        rowKey="name"
        size="small"
        columns={columns}
        dataSource={verdicts}
        pagination={false}
      />
    </DashPanel>
  );
}
