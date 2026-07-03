import { Space, Typography } from "antd";
import { FeishuRichText } from "./FeishuRichText";
import { UserProfileBlock } from "./UserProfileBlock";

interface QaPreview {
  role: "user" | "assistant";
  content: string;
}

function unquoteYamlScalar(value: string) {
  const text = value.trim();
  if (text.startsWith("'") && text.endsWith("'")) return text.slice(1, -1).replace(/''/g, "'");
  if (text.startsWith('"') && text.endsWith('"')) return text.slice(1, -1);
  return text;
}

function readYamlBlock(lines: string[], startIndex: number, marker: string) {
  const line = lines[startIndex];
  const markerIndex = line.indexOf(marker);
  if (markerIndex < 0) return "";
  const contentIndent = line.match(/^\s*/)?.[0].length ?? 0;
  const rest = line.slice(markerIndex + marker.length).trim();
  if (!rest.startsWith("|") && !rest.startsWith(">")) return unquoteYamlScalar(rest);

  const blockLines: string[] = [];
  for (let j = startIndex + 1; j < lines.length; j += 1) {
    const next = lines[j];
    const nextIndent = next.match(/^\s*/)?.[0].length ?? 0;
    if (/^\s*-\s*role:/.test(next) || (next.trim() && nextIndent <= contentIndent)) {
      break;
    }
    blockLines.push(next);
  }
  const nonEmpty = blockLines.filter((item) => item.trim());
  const indent = nonEmpty.length
    ? Math.min(...nonEmpty.map((item) => item.match(/^\s*/)?.[0].length ?? 0))
    : 0;
  return blockLines.map((item) => item.slice(indent)).join("\n").trim();
}

function parseOnlineQaPreview(yamlText: string): QaPreview[] {
  const lines = yamlText.split("\n");
  const readContentAfter = (roleIndex: number) => {
    for (let i = roleIndex + 1; i < lines.length; i += 1) {
      const line = lines[i];
      if (/^\s*-\s*role:/.test(line)) return "";
      const marker = line.indexOf("content:");
      if (marker < 0) continue;
      return readYamlBlock(lines, i, "content:");
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

function parseOnlineUserProfile(yamlText: string) {
  const lines = yamlText.split("\n");
  for (let index = 0; index < lines.length; index += 1) {
    if (!/^\s*notes:/.test(lines[index])) continue;
    const notes = readYamlBlock(lines, index, "notes:");
    const match = notes.match(/^用户档案[：:]\s*([\s\S]*)$/);
    if (!match) return "";
    return match[1].trim().split(/\n{2,}/)[0]?.trim() || "";
  }
  return "";
}

function TextBlock({ title, text }: { title: string; text: string }) {
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <Typography.Text strong>{title}</Typography.Text>
      <FeishuRichText text={text} />
    </div>
  );
}

export function OnlineCasePreview({ yamlText }: { yamlText: string }) {
  const messages = parseOnlineQaPreview(yamlText);
  const profile = parseOnlineUserProfile(yamlText);
  const rounds: Array<{ user?: string; assistant?: string }> = [];
  messages.forEach((message) => {
    if (message.role === "user" || rounds.length === 0) rounds.push({});
    const current = rounds[rounds.length - 1];
    if (message.role === "user") current.user = message.content;
    else current.assistant = message.content;
  });
  return (
    <Space direction="vertical" size={18} style={{ width: "100%" }}>
      {profile ? <UserProfileBlock text={profile} /> : null}
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
