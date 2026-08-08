import { Image, Space, Typography } from "antd";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const { Text } = Typography;

export interface ConversationMessage {
  role: string;
  content: string;
  images?: string[];
}

export interface ConversationThreadProps {
  messages: ConversationMessage[];
  maxHeight?: number;
  resolveImageSrc?: (imagePath: string) => string;
}

function assistantMarkdown(content: string): string {
  return content.replace(/<msg_break\s*\/?\s*>/gi, "\n\n---\n\n");
}

function imagePathsInMarkdown(content: string): string[] {
  return Array.from(content.matchAll(/!\[[^\]]*\]\s*\(\s*(images\/[^\s)]+)/gi), (match) => match[1]);
}

function withoutAttachedImageMarkdown(content: string, attachedImages: string[]): string {
  if (!attachedImages.length) return content;
  const imagePaths = new Set(attachedImages);
  return content
    .replace(
      /!\[[^\]]*\]\s*\(\s*(images\/[^\s)]+)(?:\s+["'][^)]*["'])?\s*\)/gi,
      (markdown, imagePath: string) => imagePaths.has(imagePath) ? "" : markdown
    )
    .replace(/\n[ \t]*\n(?:[ \t]*\n)+/g, "\n\n")
    .trim();
}

export function ConversationThread({ messages, maxHeight = 560, resolveImageSrc }: ConversationThreadProps) {
  return (
    <div style={{ maxHeight, overflowY: "auto", paddingRight: 6 }}>
      <Space direction="vertical" size={12} style={{ display: "flex" }}>
        {messages.map((m, i) => {
          const isUser = m.role === "user";
          const isAsst = m.role === "assistant";
          const roleLabel = isUser ? "用户" : isAsst ? "AI 回复" : m.role;
          const displayedContent = withoutAttachedImageMarkdown(m.content, m.images || []);
          const inlineImagePaths = imagePathsInMarkdown(displayedContent);
          const attachedImages = (m.images || []).filter((path) => !inlineImagePaths.includes(path));
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
                className={isAsst ? "conversation-bubble conversation-markdown" : "conversation-bubble"}
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
                {isAsst ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>
                    {assistantMarkdown(displayedContent)}
                  </ReactMarkdown>
                ) : resolveImageSrc ? (
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    skipHtml
                    components={{
                      img: ({ src, alt }) => (
                        <Image
                          data-testid="case-conversation-image"
                          src={src?.startsWith("images/") ? resolveImageSrc(src) : src}
                          alt={alt || "Case 图片"}
                          style={{ display: "block", maxWidth: 320, maxHeight: 420, objectFit: "contain", marginTop: 8 }}
                        />
                      ),
                    }}
                  >
                    {displayedContent}
                  </ReactMarkdown>
                ) : displayedContent}
                {resolveImageSrc && attachedImages.map((imagePath) => (
                  <Image
                    key={imagePath}
                    data-testid="case-conversation-image"
                    src={resolveImageSrc(imagePath)}
                    alt="Case 图片"
                    style={{ display: "block", maxWidth: 320, maxHeight: 420, objectFit: "contain", marginTop: 8 }}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </Space>
    </div>
  );
}
