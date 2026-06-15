import { useMemo } from "react";
import { Card, Col, Empty, Row, Statistic } from "antd";
import {
  Bar,
  BarChart,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ReviewStats, RunDetail } from "../api";
import { useFailureTagLabels } from "../failureTags";
import { DIM_LABEL } from "../labels";
import { palette } from "../theme";
import { KpiTile } from "./KpiTile";

// 失败标签饼图配色：冷灰阶 + 单一墨黑强调（取自 palette 单一信任源；Ink & Whitespace）。
const PIE_COLORS = [
  palette.chart.teal,
  palette.chart.ink,
  palette.chart.muted,
  palette.chart.faint,
];

// 图表统一降噪：隐藏轴线/刻度线，浅灰轴文字。
const AXIS_TICK = { fill: palette.muted, fontSize: 12 } as const;

// 评测概览 Tab：KPI 瓦片 + 延迟/Token 卡 + 分层级/四模块/失败标签图表。
// 全部从 run（+ reviewStats）派生，无外部副作用。
export function RunOverviewTab({
  run,
  reviewStats,
}: {
  run: RunDetail;
  reviewStats: ReviewStats | null;
}) {
  const tagLabel = useFailureTagLabels();
  const sd = run.stability_distribution || {};

  const levelData = useMemo(
    () =>
      Object.entries(run.by_level).map(([lvl, b]) => {
        const rate = b.total ? b.passed / b.total : 0;
        return {
          name: lvl,
          count: b.total,
          passed: b.passed,
          rate,
          ratePct: Number((rate * 100).toFixed(1)),
        };
      }),
    [run]
  );

  const dimData = useMemo(() => {
    const avg = (run.grading?.avg_dimension || {}) as Record<string, number>;
    return Object.entries(avg).map(([k, v]) => ({ name: DIM_LABEL[k] || k, value: Number(v) }));
  }, [run]);

  const tagData = useMemo(() => {
    const c = run.failure_tag_counter || {};
    return Object.entries(c).map(([k, v]) => ({ name: tagLabel(k), value: v as number }));
  }, [run, tagLabel]);

  return (
    <div className="ov-stack">
      <div className="kpi-grid">
        <KpiTile label="平均综合分" value={(run.grading?.avg_composite ?? 0).toFixed?.(3) ?? "-"} />
        <KpiTile
          label="通过率"
          value={`${(run.pass_rate * 100).toFixed(1)}%`}
          sub={
            run.pass_rate_ci && run.pass_rate_ci.low != null
              ? `${Math.round((run.pass_rate_ci.confidence ?? 0.95) * 100)}% CI ${(
                  run.pass_rate_ci.low * 100
                ).toFixed(1)}–${(run.pass_rate_ci.high * 100).toFixed(1)}%`
              : undefined
          }
        />
        <KpiTile
          label="硬门槛失败"
          value={run.hard_gate_failed}
          emphasize={run.hard_gate_failed > 0}
        />
        <KpiTile label="总用例" value={run.total} />
        <KpiTile
          label={`稳定性 (N=${run.n_runs})`}
          value={`${sd.stable_pass || 0}/${sd.flaky || 0}/${sd.stable_fail || 0}`}
          sub="稳过 / 抖动 / 稳挂"
        />
        {reviewStats && reviewStats.queue_total > 0 && (
          <KpiTile
            label="待审 / 队列"
            value={`${reviewStats.pending}/${reviewStats.queue_total}`}
            sub={`人审通过率 ${(reviewStats.agree_rate * 100).toFixed(0)}%`}
          />
        )}
      </div>

      <div className="ov-rule" />
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

      <div className="ov-rule" />
      <div className="ov-trio">
        <div className="ov-col">
          <Card title="分层级：数量 / 通过率" size="small">
            <ResponsiveContainer width="100%" height={220}>
              <ComposedChart data={levelData} margin={{ top: 8, right: 8, bottom: 0, left: -10 }}>
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={AXIS_TICK} />
                <YAxis
                  yAxisId="count"
                  allowDecimals={false}
                  axisLine={false}
                  tickLine={false}
                  tick={AXIS_TICK}
                />
                <YAxis
                  yAxisId="rate"
                  orientation="right"
                  domain={[0, 100]}
                  unit="%"
                  axisLine={false}
                  tickLine={false}
                  tick={AXIS_TICK}
                />
                <RTooltip formatter={(v: number, name: string) => (name === "通过率" ? `${v}%` : v)} />
                <Legend iconType="circle" />
                <Bar yAxisId="count" dataKey="count" name="用例数" fill={palette.chart.teal} radius={[3, 3, 0, 0]} maxBarSize={24} />
                <Line
                  yAxisId="rate"
                  type="monotone"
                  dataKey="ratePct"
                  name="通过率"
                  stroke={palette.chart.ink}
                  strokeWidth={1.5}
                  dot={{ r: 2.5, fill: palette.chart.ink }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </Card>
        </div>
        <div className="ov-col">
          <Card title="四模块平均分" size="small">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={dimData}>
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={AXIS_TICK} />
                <YAxis axisLine={false} tickLine={false} tick={AXIS_TICK} />
                <RTooltip />
                <Bar dataKey="value" fill={palette.chart.teal} radius={[3, 3, 0, 0]} maxBarSize={36} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </div>
        <div className="ov-col">
          <Card title="失败标签分布" size="small">
            {tagData.length === 0 ? (
              <div style={{ height: 220, display: "grid", placeItems: "center" }}>
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无失败标签" />
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={tagData}
                    dataKey="value"
                    nameKey="name"
                    cx="42%"
                    cy="50%"
                    innerRadius={42}
                    outerRadius={72}
                    paddingAngle={2}
                  >
                    {tagData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <RTooltip formatter={(v: number, n: string) => [`${v} 例`, n]} />
                  <Legend layout="vertical" align="right" verticalAlign="middle" iconType="circle" />
                </PieChart>
              </ResponsiveContainer>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
