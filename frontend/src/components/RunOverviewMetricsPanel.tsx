import { Col, Row, Statistic } from "antd";
import type { ReactNode } from "react";
import { RunDetail } from "../api/index";
import { palette } from "../theme";

const D = palette.dashboard;

function MetricCard({
  title,
  children,
  empty,
}: {
  title: string;
  children: ReactNode;
  empty?: boolean;
}) {
  return (
    <div className="runs-chart-card runs-metric-card">
      <div className="runs-chart-card__title runs-chart-card__title--solo">{title}</div>
      {empty ? (
        <div className="runs-chart-empty runs-chart-empty--compact">本次评测无相关数据</div>
      ) : (
        children
      )}
    </div>
  );
}

export function RunOverviewMetricsPanel({ run }: { run: RunDetail }) {
  const hasLatency = run.latency_summary && Object.keys(run.latency_summary).length > 0;
  const hasToken = run.token_summary && Object.keys(run.token_summary).length > 0;

  return (
    <div className="runs-duo-charts runs-duo-charts--metrics">
      <MetricCard title="性能（延迟）" empty={!hasLatency}>
        {hasLatency && (
          <Row gutter={[12, 16]}>
            <Col span={12}>
              <Statistic
                title="统计样本"
                value={run.latency_summary.count ?? "—"}
                valueStyle={{ color: D.text, fontSize: 20 }}
              />
            </Col>
            <Col span={12}>
              <Statistic
                title="平均耗时"
                value={run.latency_summary.avg_ms ?? "—"}
                suffix="ms"
                precision={0}
                valueStyle={{ color: D.text, fontSize: 20 }}
              />
            </Col>
            <Col span={8}>
              <Statistic title="中位耗时" value={run.latency_summary.median_ms ?? "—"} suffix="ms" precision={0} />
            </Col>
            <Col span={8}>
              <Statistic title="P90 耗时" value={run.latency_summary.p90_ms ?? "—"} suffix="ms" precision={0} />
            </Col>
            <Col span={8}>
              <Statistic title="最大耗时" value={run.latency_summary.max_ms ?? "—"} suffix="ms" precision={0} />
            </Col>
          </Row>
        )}
      </MetricCard>
      <MetricCard title="成本 / Token（仅观测）" empty={!hasToken}>
        {hasToken && (
          <Row gutter={[12, 16]}>
            <Col span={12}>
              <Statistic title="统计样本" value={run.token_summary.count ?? "—"} valueStyle={{ color: D.text, fontSize: 20 }} />
            </Col>
            <Col span={12}>
              <Statistic
                title="总 Token"
                value={run.token_summary.total_tokens ?? "—"}
                valueStyle={{ color: D.text, fontSize: 20 }}
              />
            </Col>
            <Col span={8}>
              <Statistic title="平均/Run" value={run.token_summary.avg_tokens_per_run ?? "—"} precision={0} />
            </Col>
            <Col span={8}>
              <Statistic
                title={`成本${run.token_summary.currency ? ` (${run.token_summary.currency})` : ""}`}
                value={run.token_summary.cost != null ? run.token_summary.cost : "N/A"}
                precision={run.token_summary.cost != null ? 4 : undefined}
              />
            </Col>
            <Col span={8}>
              <Statistic
                title="成本/Run"
                value={run.token_summary.cost_per_run != null ? run.token_summary.cost_per_run : "N/A"}
                precision={run.token_summary.cost_per_run != null ? 4 : undefined}
              />
            </Col>
          </Row>
        )}
      </MetricCard>
    </div>
  );
}
