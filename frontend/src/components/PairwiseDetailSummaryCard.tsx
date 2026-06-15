import { Card, Col, Row, Space, Statistic, Tag, Tooltip, Typography } from "antd";
import { DIM_LABEL } from "../labels";
import type { PairwiseDetail } from "../api/index";

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
  return (
    <>
      <Card>
        <Title level={4} style={{ marginTop: 0 }}>
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
        <Row gutter={16} style={{ marginTop: 16 }}>
          <Col>
            <Statistic title="B 更好（改善）" value={bWins} valueStyle={{ color: "var(--primary)" }} />
          </Col>
          <Col>
            <Statistic title="持平" value={ties} />
          </Col>
          <Col>
            <Statistic title="A 更好（回退）" value={aWins} valueStyle={{ color: "var(--fail)" }} />
          </Col>
          <Col>
            <Statistic
              title="B 胜率"
              value={total ? Math.round((bWins / total) * 100) : 0}
              suffix="%"
            />
          </Col>
          <Col>
            <Tooltip title="低置信：把 A/B 位置互换后两次判定不一致（结论受位置偏见影响、不稳），建议人工复核。">
              <Statistic
                title="低置信 · 顺序敏感"
                value={orderSensitiveN}
                valueStyle={{ color: "var(--warn)" }}
              />
            </Tooltip>
          </Col>
          <Col>
            <Tooltip title="低置信：两次一致倾向某方更优，但被医疗保守规则按安全维度降级为持平，建议人工复核。">
              <Statistic
                title="低置信 · 安全存疑"
                value={safetyDoubtN}
                valueStyle={{ color: "var(--fail)" }}
              />
            </Tooltip>
          </Col>
          <Col>
            <Tooltip title="已由人工覆写结论/维度/理由，报告统计按校准值计算。">
              <Statistic
                title="人工校准"
                value={humanCalibratedN}
                valueStyle={{ color: "var(--primary)" }}
              />
            </Tooltip>
          </Col>
        </Row>
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
      </Card>

      <Row gutter={16}>
        {["safety", "function", "experience"].map((dim) => {
          const d = byDim[dim] || { A: 0, B: 0, tie: 0 };
          return (
            <Col span={8} key={dim}>
              <Card size="small" title={`${DIM_LABEL[dim]}维度`}>
                <Space size={16}>
                  <Statistic title="B 胜" value={d.B} valueStyle={{ color: "var(--primary)" }} />
                  <Statistic title="平" value={d.tie} />
                  <Statistic title="A 胜" value={d.A} valueStyle={{ color: "var(--fail)" }} />
                </Space>
              </Card>
            </Col>
          );
        })}
      </Row>
    </>
  );
}
