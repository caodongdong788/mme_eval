import { Space, Typography } from "antd";
import type { CSSProperties, ReactNode } from "react";

interface QaPreview {
  role: "user" | "assistant";
  content: string;
}

function parseOnlineQaPreview(yamlText: string): QaPreview[] {
  const lines = yamlText.split("\n");
  const unquote = (value: string) => {
    const text = value.trim();
    if (text.startsWith("'") && text.endsWith("'")) return text.slice(1, -1).replace(/''/g, "'");
    if (text.startsWith('"') && text.endsWith('"')) return text.slice(1, -1);
    return text;
  };
  const readContentAfter = (roleIndex: number) => {
    for (let i = roleIndex + 1; i < lines.length; i += 1) {
      const line = lines[i];
      if (/^\s*-\s*role:/.test(line)) return "";
      const marker = line.indexOf("content:");
      if (marker < 0) continue;
      const contentIndent = line.match(/^\s*/)?.[0].length ?? 0;
      const rest = line.slice(marker + "content:".length).trim();
      if (!rest.startsWith("|") && !rest.startsWith(">")) return unquote(rest);

      const blockLines: string[] = [];
      for (let j = i + 1; j < lines.length; j += 1) {
        const next = lines[j];
        const nextIndent = next.match(/^\s*/)?.[0].length ?? 0;
        if (
          /^\s*-\s*role:/.test(next) ||
          (next.trim() && nextIndent <= contentIndent)
        ) {
          break;
        }
        blockLines.push(lines[j]);
      }
      const nonEmpty = blockLines.filter((item) => item.trim());
      const indent = nonEmpty.length
        ? Math.min(...nonEmpty.map((item) => item.match(/^\s*/)?.[0].length ?? 0))
        : 0;
      return blockLines.map((item) => item.slice(indent)).join("\n").trim();
    }
    return "";
  };
  const messages: QaPreview[] = [];
  lines.forEach((line, index) => {
    const match = line.match(/^\s*-\s*role:\s*(user|assistant)\s*$/);
    if (!match) return;
    const content = readContentAfter(index);
    if (content) messages.push({ role: match[1] as "user" | "assistant", content });
  });
  return messages;
}

const markdownRootStyle: CSSProperties = {
  display: "grid",
  gap: 8,
  color: "var(--ink-secondary)",
  lineHeight: 1.75,
};

const paragraphStyle: CSSProperties = {
  margin: 0,
};

const listStyle: CSSProperties = {
  margin: 0,
  paddingLeft: 22,
};

const imageWrapStyle: CSSProperties = {
  display: "block",
  margin: "4px 0",
};

const imageStyle: CSSProperties = {
  display: "block",
  maxWidth: 320,
  maxHeight: 420,
  width: "auto",
  height: "auto",
  borderRadius: 8,
  border: "1px solid var(--border-strong)",
  objectFit: "contain",
};

type MarkdownBlock =
  | { type: "paragraph"; lines: string[] }
  | { type: "ul" | "ol"; lines: string[] };

const feishuImagePattern = /\[图片[：:]\s*image_token=([A-Za-z0-9_-]+)(?:[，,]\s*尺寸=(\d+)x(\d+))?\]/g;

function normalizeMarkdownText(text: string) {
  return text
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => line.trimEnd())
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function toMarkdownBlocks(text: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = [];
  let current: MarkdownBlock | null = null;
  const flush = () => {
    if (current && current.lines.length) blocks.push(current);
    current = null;
  };

  normalizeMarkdownText(text).split("\n").forEach((rawLine) => {
    const line = rawLine.trim();
    if (!line) {
      flush();
      return;
    }
    const type = /^[-*]\s+/.test(line) ? "ul" : /^\d+[.)]\s+/.test(line) ? "ol" : "paragraph";
    if (!current || current.type !== type) {
      flush();
      current = { type, lines: [] } as MarkdownBlock;
    }
    current.lines.push(line);
  });
  flush();
  return blocks;
}

function renderBoldText(text: string, keyPrefix: string): ReactNode[] {
  return text.split(/(\*\*[^*]+?\*\*)/g).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={`${keyPrefix}-bold-${index}`}>{part.slice(2, -2).trim()}</strong>;
    }
    return part;
  });
}

function renderInlineMarkdown(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  Array.from(text.matchAll(feishuImagePattern)).forEach((match, index) => {
    if (match.index === undefined) return;
    const before = text.slice(lastIndex, match.index);
    if (before) nodes.push(...renderBoldText(before, `text-${index}`));
    const token = match[1];
    const width = match[2];
    const height = match[3];
    nodes.push(
      <span key={`image-${token}-${index}`} style={imageWrapStyle}>
        <img
          data-testid="online-case-image"
          src={`/api/benchmarks/feishu-images/${encodeURIComponent(token)}`}
          alt="飞书图片"
          title={width && height ? `${width}x${height}` : token}
          style={imageStyle}
        />
      </span>
    );
    lastIndex = match.index + match[0].length;
  });
  const rest = text.slice(lastIndex);
  if (rest) nodes.push(...renderBoldText(rest, "text-rest"));
  return nodes.length ? nodes : renderBoldText(text, "text");
}

function renderMarkdownBlocks(text: string) {
  const blocks = toMarkdownBlocks(text);
  if (!blocks.length) return <Typography.Text type="secondary">-</Typography.Text>;

  return blocks.map((block, blockIndex) => {
    if (block.type === "ul" || block.type === "ol") {
      const ListTag = block.type;
      return (
        <ListTag key={blockIndex} style={listStyle}>
          {block.lines.map((line, lineIndex) => (
            <li key={lineIndex}>{renderInlineMarkdown(line.replace(/^([-*]|\d+[.)])\s+/, ""))}</li>
          ))}
        </ListTag>
      );
    }

    return (
      <p key={blockIndex} data-testid="online-case-paragraph" style={paragraphStyle}>
        {renderInlineMarkdown(block.lines.join(""))}
      </p>
    );
  });
}

function MarkdownText({ text }: { text: string }) {
  return <div style={markdownRootStyle}>{renderMarkdownBlocks(text)}</div>;
}

function TextBlock({ title, text }: { title: string; text: string }) {
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <Typography.Text strong>{title}</Typography.Text>
      <MarkdownText text={text} />
    </div>
  );
}

export function OnlineCasePreview({ yamlText }: { yamlText: string }) {
  const messages = parseOnlineQaPreview(yamlText);
  const rounds: Array<{ user?: string; assistant?: string }> = [];
  messages.forEach((message) => {
    if (message.role === "user" || rounds.length === 0) rounds.push({});
    const current = rounds[rounds.length - 1];
    if (message.role === "user") current.user = message.content;
    else current.assistant = message.content;
  });
  return (
    <Space direction="vertical" size={18} style={{ width: "100%" }}>
      {rounds.map((round, index) => (
        <Space key={index} direction="vertical" size={12} style={{ width: "100%" }}>
          <Typography.Text type="secondary">第 {index + 1} 轮</Typography.Text>
          <TextBlock title="用户问题" text={round.user || ""} />
          <TextBlock title="Cx 回复" text={round.assistant || ""} />
        </Space>
      ))}
    </Space>
  );
}
