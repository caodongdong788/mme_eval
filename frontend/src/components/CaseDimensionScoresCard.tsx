import { Card, Descriptions, List, Tag, Typography } from "antd";
import { DIM_LABEL } from "../labels";

const { Text } = Typography;

export interface CaseDimensionScoresCardProps {
  dimensionScores?: Record<string, number | null>;
  dimensionMax?: Record<string, number>;
  scoreDeductions?: string[];
  highlightKeywords?: string[];
}

export function CaseDimensionScoresCard({
  dimensionScores = {},
  dimensionMax = {},
  scoreDeductions = [],
  highlightKeywords = [],
}: CaseDimensionScoresCardProps) {
  return (
    <Card title="维度分 / 扣分原因" size="small">
      <Descriptions column={1} size="small">
        {Object.entries(dimensionScores).map(([k, v]) => {
          const max = dimensionMax[k];
          const score = v == null ? "-" : String(v);
          return (
            <Descriptions.Item key={k} label={DIM_LABEL[k] || k}>
              {max == null ? score : `${score}/${max}`}
            </Descriptions.Item>
          );
        })}
      </Descriptions>
      {scoreDeductions.length > 0 && (
        <List
          size="small"
          header={<Text strong>扣分原因</Text>}
          dataSource={scoreDeductions}
          renderItem={(d) => <List.Item>{d}</List.Item>}
        />
      )}
      {highlightKeywords.length > 0 && (
        <div style={{ marginTop: 8 }}>
          命中关键词：{highlightKeywords.map((k) => <Tag key={k}>{k}</Tag>)}
        </div>
      )}
    </Card>
  );
}
