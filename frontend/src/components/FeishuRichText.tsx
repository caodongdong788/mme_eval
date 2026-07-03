import { Modal, Typography } from "antd";
import { useState } from "react";
import type { CSSProperties, ReactNode } from "react";

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
  cursor: "zoom-in",
  objectFit: "contain",
};

const previewImageStyle: CSSProperties = {
  display: "block",
  maxWidth: "100%",
  maxHeight: "78vh",
  width: "auto",
  height: "auto",
  margin: "0 auto",
  objectFit: "contain",
};

type MarkdownBlock =
  | { type: "paragraph"; lines: string[] }
  | { type: "ul" | "ol"; lines: string[] };

const feishuImagePattern = /\[图片[：:]\s*image_token=([A-Za-z0-9_-]+)(?:[，,]\s*尺寸=(\d+)x(\d+))?\]/g;

interface FeishuImagePreview {
  src: string;
  title: string;
}

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

  normalizeMarkdownText(text)
    .split("\n")
    .forEach((rawLine) => {
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

function renderInlineMarkdown(
  text: string,
  onPreviewImage: (preview: FeishuImagePreview) => void
): ReactNode[] {
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  Array.from(text.matchAll(feishuImagePattern)).forEach((match, index) => {
    if (match.index === undefined) return;
    const before = text.slice(lastIndex, match.index);
    if (before) nodes.push(...renderBoldText(before, `text-${index}`));
    const token = match[1];
    const width = match[2];
    const height = match[3];
    const src = `/api/benchmarks/feishu-images/${encodeURIComponent(token)}`;
    const title = width && height ? `${width}x${height}` : token;
    nodes.push(
      <span key={`image-${token}-${index}`} style={imageWrapStyle}>
        <img
          data-testid="online-case-image"
          src={src}
          alt="飞书图片"
          title={title}
          onDoubleClick={() => onPreviewImage({ src, title })}
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

function renderMarkdownBlocks(text: string, onPreviewImage: (preview: FeishuImagePreview) => void) {
  const blocks = toMarkdownBlocks(text);
  if (!blocks.length) return <Typography.Text type="secondary">-</Typography.Text>;

  return blocks.map((block, blockIndex) => {
    if (block.type === "ul" || block.type === "ol") {
      const ListTag = block.type;
      return (
        <ListTag key={blockIndex} style={listStyle}>
          {block.lines.map((line, lineIndex) => (
            <li key={lineIndex}>
              {renderInlineMarkdown(line.replace(/^([-*]|\d+[.)])\s+/, ""), onPreviewImage)}
            </li>
          ))}
        </ListTag>
      );
    }

    return (
      <p key={blockIndex} data-testid="online-case-paragraph" style={paragraphStyle}>
        {renderInlineMarkdown(block.lines.join(""), onPreviewImage)}
      </p>
    );
  });
}

export function FeishuRichText({ text }: { text: string }) {
  const [preview, setPreview] = useState<FeishuImagePreview | null>(null);

  return (
    <>
      <div style={markdownRootStyle}>{renderMarkdownBlocks(text, setPreview)}</div>
      <Modal
        centered
        footer={null}
        open={preview !== null}
        title={preview?.title || "飞书图片"}
        width="min(92vw, 1080px)"
        onCancel={() => setPreview(null)}
      >
        {preview ? (
          <img
            data-testid="online-case-image-preview"
            src={preview.src}
            alt="飞书图片预览"
            style={previewImageStyle}
          />
        ) : null}
      </Modal>
    </>
  );
}
