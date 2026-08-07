import { Col, Row, Statistic } from "antd";
import { RunDetail } from "../api/index";
import { palette } from "../theme";
import { RunsChartCard } from "./RunsChartCard";

const D = palette.dashboard;

export function RunOverviewMetricsPanel({ run }: { run: RunDetail }) {
  const hasLatency = run.latency_summary && Object.keys(run.latency_summary).length > 0;
  const hasTtft = run.ttft_summary && Object.keys(run.ttft_summary).length > 0;
  const hasToken = run.token_summary && Object.keys(run.token_summary).length > 0;
  const reliability = run.grading?.reliability || {};
  const hasReliability = Object.keys(reliability).length > 0;

  return (
    <div className="runs-duo-charts runs-duo-charts--metrics">
      <RunsChartCard title="性能（延迟）" empty={!hasLatency && !hasTtft} metric>
        {(hasLatency || hasTtft) && (
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
            <Col span={12}>
              <Statistic
                title="平均首 Token 耗时（TTFT）"
                value={run.ttft_summary?.avg_ms ?? "—"}
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
      <RunsChartCard title="可靠性（重复运行）" empty={!hasReliability} metric>
        {hasReliability && (
          <Row gutter={[12, 16]}>
            <Col span={12}>
              <Statistic title="重复次数 k" value={reliability.k ?? "—"} valueStyle={{ color: D.text, fontSize: 20 }} />
            </Col>
            <Col span={12}>
              <Statistic title="波动用例" value={reliability.flaky_cases ?? "—"} valueStyle={{ color: D.text, fontSize: 20 }} />
            </Col>
            <Col span={12}>
              <Statistic title="pass@k" value={reliability.pass_at_k ?? "—"} precision={3} valueStyle={{ color: D.text, fontSize: 20 }} />
            </Col>
            <Col span={12}>
              <Statistic title="pass^k（全成功）" value={reliability.pass_all_k ?? "—"} precision={3} valueStyle={{ color: D.text, fontSize: 20 }} />
            </Col>
          </Row>
        )}
      </RunsChartCard>
    </div>
  );
}
