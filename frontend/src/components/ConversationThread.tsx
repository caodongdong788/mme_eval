import { Space, Typography } from "antd";

const { Text } = Typography;

export interface ConversationMessage {
  role: string;
  content: string;
}

export interface ConversationThreadProps {
  messages: ConversationMessage[];
  maxHeight?: number;
}

export function ConversationThread({ messages, maxHeight = 560 }: ConversationThreadProps) {
  return (
    <div style={{ maxHeight, overflowY: "auto", paddingRight: 6 }}>
      <Space direction="vertical" size={12} style={{ display: "flex" }}>
        {messages.map((m, i) => {
          const isUser = m.role === "user";
          const isAsst = m.role === "assistant";
          const roleLabel = isUser ? "用户" : isAsst ? "AI 回复" : m.role;
          return (
            <div
              key={i}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: isAsst ? "flex-start" : isUser ? "flex-end" : "flex-start",
              }}
            >
              <Text type="secondary" style={{ fontSize: 11, marginBottom: 4 }}>
                {roleLabel}
              </Text>
              <div
                style={{
                  maxWidth: "86%",
                  padding: "10px 14px",
                  borderRadius: 12,
                  whiteSpace: "pre-wrap",
                  lineHeight: 1.6,
                  border: "1px solid var(--border)",
                  background: isAsst
                    ? "var(--panel)"
                    : isUser
                      ? "var(--primary-soft)"
                      : "var(--surface-subtle)",
                  borderColor: isUser ? "var(--primary-border)" : "var(--border)",
                }}
              >
                {m.content}
              </div>
            </div>
          );
        })}
      </Space>
    </div>
  );
}
