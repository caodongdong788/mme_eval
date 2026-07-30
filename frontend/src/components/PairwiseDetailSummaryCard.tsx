import { Col, Row, Space, Tag, Typography } from "antd";
import { DIM_LABEL } from "../labels";
import { EVALUATION_DIMENSIONS } from "../labels";
import type { PairwiseDetail } from "../api/index";
import { DashPanel } from "./DashPanel";
import { RunsKpi } from "./RunsKpi";

const { Text, Title } = Typography;

function numeric(value: unknown): number | null {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatDuration(value: number | null): string {
  if (value == null) return "N/A";
  if (value >= 1000) return `${(value / 1000).toFixed(value >= 10_000 ? 1 : 2)} s`;
  return `${Math.round(value)} ms`;
}

function formatTokens(value: number | null): string {
  if (value == null) return "N/A";
  return Math.round(value).toLocaleString("zh-CN");
}

function comparisonSub(
  a: number | null,
  b: number | null,
  formatter: (value: number | null) => string,
): { sub: string; accent?: string } {
  if (a == null || b == null) return { sub: "A/B 任一侧无可用数据" };
  const delta = b - a;
  if (delta === 0) return { sub: `A ${formatter(a)} · B 持平` };
  const pct = a ? `（${delta > 0 ? "+" : ""}${((delta / a) * 100).toFixed(1)}%）` : "";
  return {
    sub: `A ${formatter(a)} · B ${delta > 0 ? "+" : ""}${formatter(Math.abs(delta))} ${pct}`,
    // 耗时或 token 增长均表示更多资源消耗；仅提示，不影响 Pairwise 胜负。
    accent: delta > 0 ? "var(--runs-red)" : "var(--runs-green)",
  };
}

export function PairwiseDetailSummaryCard({
  detail,
  conclusion,
  runAName,
  runBName,
  aWins,
  bWins,
  ties,
  total,
  orderSensitiveN,
  safetyDoubtN,
  humanCalibratedN,
  byDim,
  diffKeys,
}: {
  detail: PairwiseDetail;
  conclusion: string;
  runAName: string;
  runBName: string;
  aWins: number;
  bWins: number;
  ties: number;
  total: number;
  orderSensitiveN: number;
  safetyDoubtN: number;
  humanCalibratedN: number;
  byDim: Record<string, { A: number; B: number; tie: number }>;
  diffKeys: string[];
}) {
  const kpiItems = [
    { label: "B 更好（改善）", value: bWins, accent: "var(--runs-purple)" },
    { label: "持平", value: ties },
    { label: "A 更好（回退）", value: aWins, accent: "var(--runs-red)" },
    { label: "B 胜率", value: total ? `${Math.round((bWins / total) * 100)}%` : "0%" },
    { label: "低置信 · 顺序敏感", value: orderSensitiveN, accent: "var(--warn)" },
    { label: "低置信 · 安全存疑", value: safetyDoubtN, accent: "var(--runs-red)" },
    { label: "人工校准", value: humanCalibratedN, accent: "var(--runs-purple)" },
  ];
  const latencyA = detail.run_a_observability?.latency_summary || {};
  const latencyB = detail.run_b_observability?.latency_summary || {};
  const tokenA = detail.run_a_observability?.token_summary || {};
  const tokenB = detail.run_b_observability?.token_summary || {};
  const observabilityItems = [
    {
      label: "平均会话耗时",
      tip: "端到端会话耗时；仅观测，不参与 Pairwise 胜负。",
      value: formatDuration(numeric(latencyB.avg_ms)),
      ...comparisonSub(numeric(latencyA.avg_ms), numeric(latencyB.avg_ms), formatDuration),
    },
    {
      label: "P90 会话耗时",
      tip: "90% 会话不超过该耗时；仅观测，不参与 Pairwise 胜负。",
      value: formatDuration(numeric(latencyB.p90_ms)),
      ...comparisonSub(numeric(latencyA.p90_ms), numeric(latencyB.p90_ms), formatDuration),
    },
    {
      label: "总 Token",
      tip: "仅统计被测 Agent，不含 Pairwise Judge；仅观测，不参与胜负。",
      value: formatTokens(numeric(tokenB.total_tokens)),
      ...comparisonSub(numeric(tokenA.total_tokens), numeric(tokenB.total_tokens), formatTokens),
    },
    {
      label: "平均 Token / 次",
      tip: "每次 Agent 会话的平均 Token；仅观测，不参与 Pairwise 胜负。",
      value: formatTokens(numeric(tokenB.avg_tokens_per_run)),
      ...comparisonSub(
        numeric(tokenA.avg_tokens_per_run),
        numeric(tokenB.avg_tokens_per_run),
        formatTokens,
      ),
    },
  ];

  return (
    <>
      <DashPanel>
        <Title level={4} style={{ marginTop: 0, color: "var(--runs-text)" }}>
          {conclusion}
        </Title>
        <Space size={8} wrap style={{ marginBottom: 4 }}>
          <Tag color="default">A（基线）= {runAName} · run #{detail.run_a_id}</Tag>
          <Tag color="green">B（本次）= {runBName} · run #{detail.run_b_id}</Tag>
        </Space>
        <div>
          <Text type="secondary">
            裁判 {detail.judge_model} · 判分尺子一致（A/B 后续均指代上述评测）
          </Text>
        </div>
        <div className="runs-kpi-row runs-kpi-row--overview" style={{ marginTop: 16, marginBottom: 0 }}>
          {kpiItems.map((item) => (
            <RunsKpi
              key={item.label}
              title={item.label}
              value={item.value}
              valueStyle={item.accent ? { color: item.accent } : undefined}
            />
          ))}
        </div>
        {diffKeys.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <Text type="secondary">被测差异：</Text>{" "}
            {diffKeys.map((k) => (
              <Tag key={k} color="blue">
                {k}
              </Tag>
            ))}
          </div>
        )}
        <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--runs-border)" }}>
          <Text strong>性能与 Token 对比</Text>
          <Text type="secondary">（仅观测，不影响 Pairwise 胜负）</Text>
          <div className="runs-kpi-row runs-kpi-row--overview" style={{ marginTop: 12, marginBottom: 0 }}>
            {observabilityItems.map((item) => (
              <RunsKpi
                key={item.label}
                title={item.label}
                tip={item.tip}
                value={item.value}
                sub={item.sub}
                valueStyle={item.accent ? { color: item.accent } : undefined}
              />
            ))}
          </div>
        </div>
      </DashPanel>

      <Row gutter={14}>
        {EVALUATION_DIMENSIONS.map((dim) => {
          const d = byDim[dim] || { A: 0, B: 0, tie: 0 };
          return (
            <Col xs={24} sm={12} xl={6} key={dim}>
              <DashPanel title={`${DIM_LABEL[dim]}维度`}>
                <Space size={16}>
                  <RunsKpi
                    title="B 胜"
                    value={d.B}
                    valueStyle={{ color: "var(--runs-purple)" }}
                  />
                  <RunsKpi title="平" value={d.tie} />
                  <RunsKpi
                    title="A 胜"
                    value={d.A}
                    valueStyle={{ color: "var(--runs-red)" }}
                  />
                </Space>
              </DashPanel>
            </Col>
          );
        })}
      </Row>
    </>
  );
}
