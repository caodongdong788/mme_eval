import { Alert, Col, Row, Space, Tag, Typography } from "antd";
import type { ReactNode } from "react";
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

function comparisonValue(a: number | null, b: number | null, formatter: (value: number | null) => string): ReactNode {
  return (
    <span className="pairwise-observability-values">
      <span className="pairwise-observability-values__row">
        <span className="pairwise-observability-values__label">A（基线）</span>
        <strong>{formatter(a)}</strong>
      </span>
      <span className="pairwise-observability-values__row">
        <span className="pairwise-observability-values__label">B（本次）</span>
        <strong>{formatter(b)}</strong>
      </span>
    </span>
  );
}

function comparisonSub(
  a: number | null,
  b: number | null,
  formatter: (value: number | null) => string,
): { value: ReactNode; sub: ReactNode } {
  const value = comparisonValue(a, b, formatter);
  if (a == null || b == null) {
    return { value, sub: <span>缺少一侧数据，暂无法计算变化</span> };
  }
  const delta = b - a;
  if (delta === 0) {
    return { value, sub: <span className="pairwise-observability-delta pairwise-observability-delta--neutral">较 A 持平（0.0%）</span> };
  }
  const direction = delta > 0 ? "增加" : "减少";
  const percentage = a === 0 ? "基线为 0，无法计算比例" : `${delta > 0 ? "+" : ""}${((delta / a) * 100).toFixed(1)}%`;
  return {
    value,
    // 耗时或 token 增长均表示更多资源消耗；仅提示，不影响 Pairwise 胜负。
    sub: (
      <span className={`pairwise-observability-delta pairwise-observability-delta--${delta > 0 ? "increase" : "decrease"}`}>
        较 A {direction} {formatter(Math.abs(delta))}（{percentage}）
      </span>
    ),
  };
}

function averageSessionDurationComparison(
  a: number | null,
  b: number | null,
): { value: ReactNode; sub: ReactNode } {
  const value = comparisonValue(a, b, formatDuration);
  if (a == null || b == null) {
    return { value, sub: <span>缺少一侧数据，暂无法计算单次会话变化</span> };
  }
  const delta = b - a;
  if (delta === 0) {
    return {
      value,
      sub: <span className="pairwise-observability-delta pairwise-observability-delta--neutral">单次会话平均耗时持平（0.0%）</span>,
    };
  }
  const direction = delta > 0 ? "变慢" : "变快";
  const percentage = a === 0 ? "基线为 0，无法计算比例" : `${delta > 0 ? "+" : ""}${((delta / a) * 100).toFixed(1)}%`;
  return {
    value,
    sub: (
      <span className={`pairwise-observability-delta pairwise-observability-delta--${delta > 0 ? "increase" : "decrease"}`}>
        单次会话平均{direction} {formatDuration(Math.abs(delta))}（{percentage}）
      </span>
    ),
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
      label: "平均单次会话耗时",
      tip: "有效会话的端到端耗时平均值；增量为 B、A 两侧平均单次会话耗时之差，不计算整批用例的总耗时。仅观测，不参与 Pairwise 胜负。",
      ...averageSessionDurationComparison(numeric(latencyA.avg_ms), numeric(latencyB.avg_ms)),
    },
    {
      label: "P90 会话耗时",
      tip: "90% 会话不超过该耗时；仅观测，不参与 Pairwise 胜负。",
      ...comparisonSub(numeric(latencyA.p90_ms), numeric(latencyB.p90_ms), formatDuration),
    },
    {
      label: "总 Token",
      tip: "仅统计被测 Agent，不含 Pairwise Judge；仅观测，不参与胜负。",
      ...comparisonSub(numeric(tokenA.total_tokens), numeric(tokenB.total_tokens), formatTokens),
    },
    {
      label: "平均 Token / 次",
      tip: "每次 Agent 会话的平均 Token；仅观测，不参与 Pairwise 胜负。",
      ...comparisonSub(
        numeric(tokenA.avg_tokens_per_run),
        numeric(tokenB.avg_tokens_per_run),
        formatTokens,
      ),
    },
  ];
  const ragScope = detail.summary?.rag_scope;

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
        {detail.scope === "rag_triggered_only" && ragScope && (
          <Alert
            type="info"
            showIcon
            style={{ marginTop: 14 }}
            message={`本结论只基于 ${ragScope.rag_side} 侧（RAG 组）真实触发 RAG 的 ${ragScope.selected_cases} 题`}
            description={`共有 ${ragScope.common_cases} 题，排除未触发或链路未知 ${ragScope.excluded_cases} 题（未知 ${ragScope.unknown_cases} 题）。`}
          />
        )}
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
          <Text type="secondary">
            （{detail.scope === "rag_triggered_only" ? "仅统计上述 RAG 触发题；" : ""}仅观测，不影响 Pairwise 胜负）
          </Text>
          <div className="runs-kpi-row runs-kpi-row--overview" style={{ marginTop: 12, marginBottom: 0 }}>
            {observabilityItems.map((item) => (
              <RunsKpi
                key={item.label}
                title={item.label}
                tip={item.tip}
                value={item.value}
                sub={item.sub}
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
