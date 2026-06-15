import { Col, Row, Statistic } from "antd";
import { RunDetail } from "../api/index";
import { palette } from "../theme";

export function RunOverviewMetricsPanel({ run }: { run: RunDetail }) {
  return (
    <div className="ov-duo">
      <div className="ov-col">
        <div className="ov-section-title">性能（延迟）</div>
        {run.latency_summary && Object.keys(run.latency_summary).length > 0 ? (
          <Row gutter={[12, 16]}>
            <Col span={12}>
              <Statistic title="统计样本" value={run.latency_summary.count ?? "-"} />
            </Col>
            <Col span={12}>
              <Statistic title="平均耗时" value={run.latency_summary.avg_ms ?? "-"} suffix="ms" precision={0} />
            </Col>
            <Col span={8}>
              <Statistic title="中位耗时" value={run.latency_summary.median_ms ?? "-"} suffix="ms" precision={0} />
            </Col>
            <Col span={8}>
              <Statistic title="P90 耗时" value={run.latency_summary.p90_ms ?? "-"} suffix="ms" precision={0} />
            </Col>
            <Col span={8}>
              <Statistic title="最大耗时" value={run.latency_summary.max_ms ?? "-"} suffix="ms" precision={0} />
            </Col>
          </Row>
        ) : (
          <span style={{ color: palette.muted }}>本次评测无延迟数据</span>
        )}
      </div>
      <div className="ov-col">
        <div className="ov-section-title">成本 / Token（仅观测）</div>
        {run.token_summary && Object.keys(run.token_summary).length > 0 ? (
          <Row gutter={[12, 16]}>
            <Col span={12}>
              <Statistic title="统计样本" value={run.token_summary.count ?? "-"} />
            </Col>
            <Col span={12}>
              <Statistic title="总 Token" value={run.token_summary.total_tokens ?? "-"} />
            </Col>
            <Col span={8}>
              <Statistic title="平均/Run" value={run.token_summary.avg_tokens_per_run ?? "-"} precision={0} />
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
        ) : (
          <span style={{ color: palette.muted }}>本次评测无 token 数据</span>
        )}
      </div>
    </div>
  );
}
