import { Table, Tag, Typography } from "antd";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { GuidelineScore } from "../api";
import { DIM_LABEL } from "../labels";
import { DashPanel } from "./DashPanel";

function EvidenceQuote({ value }: { value: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{ p: ({ children }) => <span>{children}</span> }}
    >
      {value}
    </ReactMarkdown>
  );
}

function GuidelineDecision({ row }: { row: GuidelineScore }) {
  const deduction = row.deduction ?? Math.max(0, row.max_score - row.score);
  const deducted = row.applicable !== false && deduction > 0;
  if (!deducted) {
    return <Typography.Text type="secondary">{row.reason || "符合要求，未扣分"}</Typography.Text>;
  }
  return (
    <div data-testid={`guideline-decision-${row.id}`}>
      <div>
        <Typography.Text type="danger">
          <strong>扣分理由：</strong>{row.reason || "未满足指南要求"}
        </Typography.Text>
      </div>
      <div style={{ marginTop: 8 }}>
        <Typography.Text strong>扣分原文：</Typography.Text>
        {row.evidence?.length ? (
          row.evidence.map((quote, index) => (
            <div key={`${index}-${quote}`} style={{ marginTop: index === 0 ? 0 : 4 }}>
              <EvidenceQuote value={quote} />
            </div>
          ))
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        )}
      </div>
    </div>
  );
}

export function GuidelineScoresTable({ scores }: { scores: GuidelineScore[] }) {
  if (!scores.length) return null;
  return (
    <DashPanel title="指南覆盖评分" bodyClassName="dash-panel__body--flush">
      <Table
        className="dash-table"
        rowKey="id"
        size="small"
        pagination={false}
        dataSource={scores}
        columns={[
          {
            title: "检查点与规则",
            render: (_, row) => (
              <div>
                <ol style={{ margin: 0, paddingInlineStart: 18 }}>
                  {(row.checkpoints || row.criterion || []).map((point) => <li key={point}>{point}</li>)}
                </ol>
                {row.deduction_rule ? <Typography.Text type="secondary">{row.deduction_rule}</Typography.Text> : null}
                {row.reference_answers?.length ? (
                  <div className="guideline-recommended-answer">
                    <Typography.Text strong>推荐回答：</Typography.Text>
                    {row.reference_answers.join("；")}
                  </div>
                ) : null}
              </div>
            ),
          },
          {
            title: "绑定维度",
            dataIndex: "dimension",
            width: 180,
            render: (dimension: string) => DIM_LABEL[dimension] || dimension || "未关联维度",
          },
          {
            title: "得分",
            width: 100,
            render: (_, row) => (
              row.applicable === false ? <Tag>未触发</Tag> : (
                <Tag color={row.score === row.max_score ? "green" : "orange"}>
                  {row.score}/{row.max_score}{row.deduction ? `（扣 ${row.deduction}）` : ""}
                </Tag>
              )
            ),
          },
          {
            title: "判定理由",
            render: (_, row) => <GuidelineDecision row={row} />,
          },
        ]}
      />
    </DashPanel>
  );
}
