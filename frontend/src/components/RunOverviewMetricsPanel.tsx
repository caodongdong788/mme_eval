import { Col, Row, Statistic } from "antd";
import { RunDetail } from "../api/index";
import { palette } from "../theme";
import { RunsChartCard } from "./RunsChartCard";

const D = palette.dashboard;

export function RunOverviewMetricsPanel({ run }: { run: RunDetail }) {
  const hasLatency = run.latency_summary && Object.keys(run.latency_summary).length > 0;
  const hasToken = run.token_summary && Object.keys(run.token_summary).length > 0;

  return (
    <div className="runs-duo-charts runs-duo-charts--metrics">
      <RunsChartCard title="性能（延迟）" empty={!hasLatency} metric>
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
            <Col span={12}>
              <Statistic
                title="中位 (P50)"
                value={run.latency_summary.median_ms ?? run.latency_summary.p50_ms ?? "—"}
                suffix="ms"
                precision={0}
                valueStyle={{ color: D.text, fontSize: 20 }}
              />
            </Col>
            <Col span={12}>
              <Statistic
                title="P90"
                value={run.latency_summary.p90_ms ?? run.latency_summary.p95_ms ?? "—"}
                suffix="ms"
                precision={0}
                valueStyle={{ color: D.text, fontSize: 20 }}
              />
            </Col>
          </Row>
        )}
      </RunsChartCard>
      <RunsChartCard title="Token 消耗" empty={!hasToken} metric>
        {hasToken && (
          <Row gutter={[12, 16]}>
            <Col span={12}>
              <Statistic
                title="总 Token"
                value={
                  run.token_summary.total_tokens ?? run.token_summary.total ?? "—"
                }
                valueStyle={{ color: D.text, fontSize: 20 }}
              />
            </Col>
            <Col span={12}>
              <Statistic
                title="平均每 run"
                value={
                  run.token_summary.avg_tokens_per_run ??
                  run.token_summary.avg_per_case ??
                  "—"
                }
                precision={0}
                valueStyle={{ color: D.text, fontSize: 20 }}
              />
            </Col>
          </Row>
        )}
      </RunsChartCard>
    </div>
  );
}
