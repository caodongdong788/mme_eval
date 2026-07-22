import { Tag, Typography } from "antd";

type ContextKind = "profile" | "fact";

export interface ConversationContextInitialState {
  user_profile?: Record<string, unknown>;
  Timeline?: unknown;
  timeline?: unknown;
}

interface AssistantMessage {
  role: string;
  content: string;
}

interface ContextReference {
  kind: ContextKind;
  label: string;
  content: unknown;
  turns: number[];
  evidence: string;
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function hasContent(value: unknown): boolean {
  if (value === null || value === undefined || value === "") return false;
  if (Array.isArray(value)) return value.some(hasContent);
  if (typeof value === "object") return Object.values(record(value)).some(hasContent);
  return true;
}

function renderValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(renderValue).filter(Boolean).join("、");
  if (value && typeof value === "object") {
    return Object.entries(record(value))
      .filter(([, item]) => hasContent(item))
      .map(([key, item]) => `${key}：${renderValue(item)}`)
      .join("；");
  }
  return String(value ?? "");
}

function comparable(value: string): string {
  return value
    .toLocaleLowerCase()
    .replace(/[\s，。；、：:,.!?！？（）()【】\[\]「」『』"'`*—\-]/g, "");
}

function candidatePhrases(value: unknown): string[] {
  const text = renderValue(value);
  return text
    .split(/[\n，。；、：:,.!?！？]/)
    .map((part) => part.trim())
    .filter((part) => comparable(part).length >= 4)
    .sort((a, b) => comparable(b).length - comparable(a).length);
}

function timelineFacts(value: unknown): Array<{ label: string; content: unknown }> {
  if (Array.isArray(value)) return value.flatMap(timelineFacts);
  const item = record(value);
  if (!Object.keys(item).length) return [];
  if (typeof item.label === "string" && hasContent(item.content)) {
    return [{ label: item.label, content: item.content }];
  }
  return Object.entries(item)
    .filter(([, content]) => hasContent(content))
    .map(([label, content]) => ({ label, content }));
}

function referenceTurns(content: unknown, assistantMessages: AssistantMessage[]): { turns: number[]; evidence: string } | null {
  const phrases = candidatePhrases(content);
  for (const phrase of phrases) {
    const needle = comparable(phrase);
    const turns = assistantMessages.flatMap((message, index) => (
      comparable(message.content).includes(needle) ? [index + 1] : []
    ));
    if (turns.length) return { turns, evidence: phrase };
  }
  return null;
}

export function findConversationContextReferences(
  initialState: ConversationContextInitialState | undefined,
  messages: AssistantMessage[],
): ContextReference[] {
  const assistantMessages = messages.filter((message) => message.role === "assistant");
  if (!assistantMessages.length || !initialState) return [];

  const references: ContextReference[] = [];
  for (const [label, content] of Object.entries(initialState.user_profile || {})) {
    const match = referenceTurns(content, assistantMessages);
    if (match) references.push({ kind: "profile", label, content, ...match });
  }
  for (const fact of timelineFacts(initialState.Timeline ?? initialState.timeline)) {
    const match = referenceTurns(fact.content, assistantMessages);
    if (match) references.push({ kind: "fact", ...fact, ...match });
  }
  return references;
}

function ReferenceRows({ references, kind }: { references: ContextReference[]; kind: ContextKind }) {
  const rows = references.filter((reference) => reference.kind === kind);
  if (!rows.length) {
    return <div className="conversation-context-empty">本次回复未发现可确认的文本引用</div>;
  }
  return (
    <div className="conversation-context-rows">
      {rows.map((reference, index) => (
        <article className="conversation-context-row" key={`${reference.label}-${index}`}>
          <div className="conversation-context-row__head">
            <strong>{reference.label}</strong>
            <span>{reference.turns.map((turn) => <Tag key={turn}>回复 {turn}</Tag>)}</span>
          </div>
          <p>{renderValue(reference.content)}</p>
          <small>命中：{reference.evidence}</small>
        </article>
      ))}
    </div>
  );
}

export function ConversationContextReferences({
  initialState,
  messages,
}: {
  initialState?: ConversationContextInitialState;
  messages: AssistantMessage[];
}) {
  const references = findConversationContextReferences(initialState, messages);
  const profileCount = references.filter((reference) => reference.kind === "profile").length;
  const factCount = references.filter((reference) => reference.kind === "fact").length;
  return (
    <div className="conversation-context-references">
      <p className="conversation-context-note">仅展示回复正文中可确认命中的预置上下文；未命中不代表未注入。</p>
      <section>
        <header><Typography.Text strong>引用的用户档案</Typography.Text><span>{profileCount} 项</span></header>
        <ReferenceRows references={references} kind="profile" />
      </section>
      <section>
        <header><Typography.Text strong>引用的过往事实</Typography.Text><span>{factCount} 条</span></header>
        <ReferenceRows references={references} kind="fact" />
      </section>
    </div>
  );
}
