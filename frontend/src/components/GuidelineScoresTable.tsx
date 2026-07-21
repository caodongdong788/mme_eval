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
          { title: "指南项", dataIndex: "criterion" },
          { title: "绑定维度", dataIndex: "dimension", width: 180 },
          {
            title: "得分",
            width: 100,
            render: (_, row) => (
              <Tag color={row.score === row.max_score ? "green" : "orange"}>
                {row.score}/{row.max_score}
              </Tag>
            ),
          },
          {
            title: "判定理由",
            render: (_, row) => (
              <div>
                <div>{row.reason || "—"}</div>
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
