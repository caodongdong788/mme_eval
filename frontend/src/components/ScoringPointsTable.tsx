import { Table, Tag, Typography } from "antd";
import { CaseVerdict, scoringPointWeight } from "../utils/caseJudging";
import { DashPanel } from "./DashPanel";

const { Text } = Typography;

export interface ScoringPointsTableProps {
  scoringPoints: CaseVerdict[];
}

export function ScoringPointsTable({ scoringPoints }: ScoringPointsTableProps) {
  if (scoringPoints.length === 0) return null;

  return (
    <DashPanel title="得分点" bodyClassName="dash-panel__body--flush">
      <Table
        className="dash-table"
        rowKey="name"
        size="small"
        columns={[
          { title: "得分点", dataIndex: "name", width: 180 },
          {
            title: "命中",
            dataIndex: "passed",
            width: 64,
            render: (p: boolean) => (p ? "✅" : "❌"),
          },
          {
            title: "分 / 罚则",
            width: 120,
            render: (_: unknown, v: CaseVerdict) => {
              const w = scoringPointWeight(v);
              if (w != null && w < 0) {
                return (v.score ?? 0) < 0 ? (
                  <Tag color="red">已扣 {w}</Tag>
                ) : (
                  <Tag color="green">未触发 · 罚则 {w}</Tag>
                );
              }
              return `${v.score}/${v.max_score}`;
            },
          },
          {
            title: "说明",
            render: (_: unknown, v: CaseVerdict) => {
              const isPoint = /\.point\d+$/.test(v?.name || "");
              const ev: string = (isPoint && v?.evidence && v.evidence[0]) || "";
              return (
                <div>
                  {ev ? <div>{ev}</div> : null}
                  {v.reason ? (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {v.reason}
                    </Text>
                  ) : null}
                </div>
              );
            },
          },
        ]}
        dataSource={scoringPoints}
        pagination={false}
      />
    </DashPanel>
  );
}
