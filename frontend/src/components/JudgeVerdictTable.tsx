import { Space, Table, Tag, Typography } from "antd";
import { useJudgeVerdictLabels } from "../hooks/useConfigLabelMap";
import { CaseVerdict } from "../utils/caseJudging";
import { DashPanel } from "./DashPanel";

const { Text } = Typography;

export interface JudgeVerdictTableProps {
  verdicts: CaseVerdict[];
  tagLabel: (tag: string) => string;
  dimensionRawScores?: Record<string, number | null>;
  dimensionScores?: Record<string, number | null>;
  dimensionMax?: Record<string, number>;
  scoreDeductions?: string[];
}

function dimensionKey(name: string): string | null {
  return name.startsWith("dimension.") ? name.slice("dimension.".length) : null;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function JudgeVerdictTable({
  verdicts,
  tagLabel,
  dimensionRawScores = {},
  dimensionScores = {},
  dimensionMax = {},
  scoreDeductions = [],
}: JudgeVerdictTableProps) {
  const judgeLabel = useJudgeVerdictLabels();
  const dimensionVerdicts = verdicts.filter((verdict) => dimensionKey(verdict.name));
  const deductionsFor = (name: string): string[] => {
    const key = dimensionKey(name);
    if (!key) return [];
    const prefix = new RegExp(`^${escapeRegExp(key)}(?:\\s+|[：:])`);
    return scoreDeductions
      .filter((item) => prefix.test(item))
      .map((item) => item.replace(prefix, ""));
  };
  const columns = [
    {
      title: "维度",
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
      width: 110,
      render: (_: unknown, v: CaseVerdict) => {
        const key = dimensionKey(v.name);
        if (!key) return v.max_score ? `${v.score}/${v.max_score}` : "-";
        const finalScore = dimensionScores[key] ?? v.score;
        const rawScore = dimensionRawScores[key] ?? v.score;
        const maxScore = dimensionMax[key] ?? v.max_score;
        if (finalScore == null || maxScore == null) return "-";
        const guidelineDeduction = rawScore == null ? 0 : Math.max(0, rawScore - finalScore);
        return (
          <Space direction="vertical" size={0}>
            <span>{`最终 ${finalScore}/${maxScore}`}</span>
            {guidelineDeduction > 0 ? (
              <Text type="secondary" style={{ fontSize: 11 }}>
                {`维度原始 ${rawScore}/${maxScore} · 指南 -${guidelineDeduction}分`}
              </Text>
            ) : null}
          </Space>
        );
      },
    },
    {
      title: "判定与扣分原因",
      dataIndex: "reason",
      render: (reason: string | undefined, verdict: CaseVerdict) => {
        const deductions = deductionsFor(verdict.name);
        return (
          <div className="judge-reason">
            <span>{reason || "—"}</span>
            {deductions.length ? (
              <div className="judge-reason__deductions">
                <strong>扣分原因</strong>
                {deductions.map((item, index) => <div key={`${item}-${index}`}>{item}</div>)}
              </div>
            ) : null}
          </div>
        );
      },
    },
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
  ];

  return (
    <DashPanel title="维度评分" bodyClassName="dash-panel__body--flush">
      <Table
        className="dash-table"
        rowKey="name"
        size="small"
        columns={columns}
        dataSource={dimensionVerdicts}
        pagination={false}
      />
    </DashPanel>
  );
}
