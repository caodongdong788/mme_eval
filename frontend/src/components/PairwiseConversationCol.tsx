import { Card, Empty, Space, Tag, Typography } from "antd";
import { ArrowRightOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import type { ConversationMessage } from "./ConversationThread";

const { Text } = Typography;

export function PairwiseConversationCol({
  messages,
  runId,
  sampleId,
  side,
  runName,
  comparisonId,
}: {
  messages: ConversationMessage[];
  runId: number;
  sampleId: string;
  side: "A" | "B";
  runName: string;
  comparisonId: number;
}) {
  return (
    <Card
      size="small"
      title={
        <span>
          <Tag color={side === "B" ? "green" : "default"} style={{ marginInlineEnd: 6 }}>
            {side}
          </Tag>
          {runName}
        </span>
      }
      extra={
        <Link
          to={`/runs/${runId}/cases/${encodeURIComponent(sampleId)}`}
          state={{
            from: {
              to: `/pairwise/${comparisonId}`,
              state: { expandedKey: sampleId },
              label: "对比明细",
            },
          }}
        >
          用例明细 <ArrowRightOutlined />
        </Link>
      }
      styles={{ body: { maxHeight: 420, overflowY: "auto" } }}
    >
      <Space direction="vertical" size={8} style={{ display: "flex" }}>
        {messages.map((m, i) => {
          const isUser = m.role === "user";
          return (
            <div key={i} style={{ alignSelf: isUser ? "flex-start" : "stretch" }}>
              <Text type="secondary" style={{ fontSize: 11 }}>
                {isUser ? "用户" : m.role === "assistant" ? "AI 回复" : m.role}
              </Text>
              <div
                style={{
                  whiteSpace: "pre-wrap",
                  background: isUser ? "var(--surface-chip)" : "transparent",
                  border: isUser ? "none" : "1px solid var(--border)",
                  borderRadius: 8,
                  padding: "6px 10px",
                  fontSize: 13,
                }}
              >
                {m.content}
              </div>
            </div>
          );
        })}
        {messages.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />}
      </Space>
    </Card>
  );
}
