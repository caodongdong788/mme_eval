import { Alert, Button, Card, Input, List, Radio, Space, Typography } from "antd";
import { Annotation } from "../api/index";

const { Text } = Typography;

export interface HumanReviewCardProps {
  verdict: "agree" | "override";
  onVerdictChange: (verdict: "agree" | "override") => void;
  suggestion: string;
  onSuggestionChange: (value: string) => void;
  comment: string;
  onCommentChange: (value: string) => void;
  saving: boolean;
  onSubmit: () => void;
  onOpenEditor: () => void;
  annotations: Annotation[];
}

export function HumanReviewCard({
  verdict,
  onVerdictChange,
  suggestion,
  onSuggestionChange,
  comment,
  onCommentChange,
  saving,
  onSubmit,
  onOpenEditor,
  annotations,
}: HumanReviewCardProps) {
  return (
    <Card title="人工裁定（HITL）" size="small">
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="裁定为旁路记录，不会修改机器判分（verdict / 综合分 / 上线判定均保持不变）。若要按新判据重判，可用「推翻」后就地「改判据(YAML)」改这一条、先「试判预览」验证，满意后覆盖当前 benchmark 或另存新集；要让某个 run 反映新判据需另行「重判」。"
      />
      <Space direction="vertical" style={{ width: "100%" }}>
        <Radio.Group value={verdict} onChange={(e) => onVerdictChange(e.target.value)}>
          <Radio.Button value="agree">同意机器</Radio.Button>
          <Radio.Button value="override">推翻机器</Radio.Button>
        </Radio.Group>
        {verdict === "override" && (
          <Space>
            <Text type="secondary">想真正改判据并重判？</Text>
            <Button size="small" type="primary" ghost onClick={onOpenEditor}>
              改判据(YAML)
            </Button>
          </Space>
        )}
        <Input.TextArea
          value={suggestion}
          onChange={(e) => onSuggestionChange(e.target.value)}
          placeholder="建议修正（可选，如：橘皮征属红旗，应建议立即就医）"
          autoSize={{ minRows: 2, maxRows: 4 }}
        />
        <Input.TextArea
          value={comment}
          onChange={(e) => onCommentChange(e.target.value)}
          placeholder="备注（可选）"
          autoSize={{ minRows: 1, maxRows: 3 }}
        />
        <Button type="primary" loading={saving} onClick={onSubmit}>
          提交裁定
        </Button>
      </Space>
      {annotations.length > 0 && (
        <List
          style={{ marginTop: 16 }}
          size="small"
          header={<Text strong>历史裁定（{annotations.length}）</Text>}
          dataSource={annotations}
          renderItem={(a) => (
            <List.Item>
              <Space direction="vertical" size={2} style={{ width: "100%" }}>
                <Space>
                  <span
                    className={`status-dot status-dot--${a.verdict === "agree" ? "pass" : "warn"}`}
                  >
                    {a.verdict === "agree" ? "同意机器" : "推翻机器"}
                  </span>
                  <Text type="secondary">{a.reviewer || "匿名"}</Text>
                  <Text type="secondary">{a.created_at?.replace("T", " ").slice(0, 16)}</Text>
                </Space>
                {a.suggestion && <Text>建议：{a.suggestion}</Text>}
                {a.comment && <Text type="secondary">备注：{a.comment}</Text>}
              </Space>
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}
