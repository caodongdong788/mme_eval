import { Col, Row, Space, Tag, Typography } from "antd";
import { DIM_LABEL } from "../labels";
import type { PairwiseDetail } from "../api/index";
import { DashPanel } from "./DashPanel";
import { RunsKpi } from "./RunsKpi";

const { Text, Title } = Typography;

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
      </DashPanel>

      <Row gutter={14}>
        {["safety", "function", "experience"].map((dim) => {
          const d = byDim[dim] || { A: 0, B: 0, tie: 0 };
          return (
            <Col span={8} key={dim}>
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
