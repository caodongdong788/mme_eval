import { Table, Tag, Typography } from "antd";
import type { GuidelineScore } from "../api";
import { DashPanel } from "./DashPanel";

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
              </div>
            ),
          },
          { title: "绑定维度", dataIndex: "dimension", width: 180 },
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
            render: (_, row) => (
              <div>
                <div>{row.reason || "—"}</div>
                {row.missed_points?.length ? <Typography.Text type="danger">遗漏：{row.missed_points.join("；")}</Typography.Text> : null}
                {row.evidence?.length ? (
                  <Typography.Text type="secondary">{row.evidence.join("；")}</Typography.Text>
                ) : null}
              </div>
            ),
          },
        ]}
      />
    </DashPanel>
  );
}
