import { Card, Spin } from "antd";
import { LoadingOutlined } from "@ant-design/icons";
import type { PairwiseDetail } from "../api/index";

export function PairwiseDetailRunningCard({
  detail,
  runAName,
  runBName,
  doneCases,
  totalCases,
  pct,
}: {
  detail: PairwiseDetail;
  runAName: string;
  runBName: string;
  doneCases: number;
  totalCases: number;
  pct: number;
}) {
  return (
    <Card className="pw-running" styles={{ body: { padding: 20 } }}>
      <div className="pw-running__head">
        <Spin indicator={<LoadingOutlined style={{ fontSize: 20 }} spin />} />
        <div className="pw-running__meta">
          <div className="pw-running__title">逐题对比进行中</div>
          <div className="pw-running__sub">
            B({runBName}) vs A({runAName}) · 裁判 {detail.judge_model}
          </div>
        </div>
        <div className="pw-running__count mono">
          {doneCases}
          <span className="pw-running__count-total"> / {totalCases || "…"}</span>
        </div>
      </div>
      <div className="pw-progress">
        <div
          className={`pw-progress__bar${totalCases ? "" : " pw-progress__bar--indeterminate"}`}
          style={totalCases ? { width: `${pct}%` } : undefined}
        />
      </div>
    </Card>
  );
}
