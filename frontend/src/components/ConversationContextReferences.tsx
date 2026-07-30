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
    .replace(/[\s，。；、：:,.!?！？（）()【】\u005B\u005D「」『』"'`*—\u002D]/g, "");
}

function longestCommonExcerpt(left: string, right: string): string {
  const a = comparable(left);
  const b = comparable(right);
  if (!a || !b) return "";
  let previous = new Array<number>(b.length + 1).fill(0);
  let bestLength = 0;
  let bestEnd = 0;
  for (let row = 1; row <= a.length; row += 1) {
    const current = new Array<number>(b.length + 1).fill(0);
    for (let column = 1; column <= b.length; column += 1) {
      if (a[row - 1] === b[column - 1]) {
        current[column] = previous[column - 1] + 1;
        if (current[column] > bestLength) {
          bestLength = current[column];
          bestEnd = row;
        }
      }
    }
    previous = current;
  }
  // 六个连续字符可排除常见药名、泛化的“产后恢复”等偶然重合；同时容忍
  // 模型在“医生提示过产后 5 天”这类句子中插入一个语气词。
  return bestLength >= 6 ? a.slice(bestEnd - bestLength, bestEnd) : "";
}

function fuzzyExcerpt(left: string, right: string): string {
  const directExcerpt = longestCommonExcerpt(left, right);
  if (directExcerpt) return directExcerpt;

  const a = comparable(left);
  const b = comparable(right);
  if (a.length < 4 || b.length < 4) return "";

  // 对较短的改写（例如“尽快恢复服用”→“尽快恢复吃”）使用二元片段重叠。
  // 这并不是要求整句相同；但至少要求三个连续的二元片段、并覆盖较短文本的
  // 40%，避免“产后”“用药”等常见词造成误命中。
  const bigrams = (text: string) => new Set(
    Array.from({ length: text.length - 1 }, (_, index) => text.slice(index, index + 2)),
  );
  const sourceBigrams = bigrams(a);
  const replyBigrams = bigrams(b);
  const shared = [...sourceBigrams].filter((gram) => replyBigrams.has(gram));
  const coverage = shared.length / Math.min(sourceBigrams.size, replyBigrams.size);
  if (shared.length < 3 || coverage < 0.4) return "";

  // 用最长公共片段展示可核对的证据。即使片段不足六字，前述重叠阈值已保证
  // 它不是单个泛化词带来的偶然相同。
  let best = "";
  for (let start = 0; start < a.length; start += 1) {
    for (let end = start + 2; end <= a.length; end += 1) {
      const candidate = a.slice(start, end);
      if (candidate.length > best.length && b.includes(candidate)) best = candidate;
    }
  }
  return best;
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
  const sourceText = renderValue(content);
  let evidence = "";
  const turns = assistantMessages.flatMap((message, index) => {
    const excerpt = fuzzyExcerpt(sourceText, message.content);
    if (!excerpt) return [];
    if (excerpt.length > evidence.length) evidence = excerpt;
    return [index + 1];
  });
  return turns.length ? { turns, evidence } : null;
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
          <small>模糊命中：{reference.evidence}</small>
        </article>
      ))}
    </div>
  );
}

function InjectedRows({
  entries,
  emptyText,
}: {
  entries: Array<{ label: string; content: unknown }>;
  emptyText: string;
}) {
  if (!entries.length) return <div className="conversation-context-empty">{emptyText}</div>;
  return (
    <div className="conversation-context-rows conversation-context-rows--injected">
      {entries.map((entry, index) => (
        <article className="conversation-context-row" key={`${entry.label}-${index}`}>
          <div className="conversation-context-row__head"><strong>{entry.label}</strong><Tag color="blue">已注入</Tag></div>
          <p>{renderValue(entry.content)}</p>
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
  const profileEntries = Object.entries(initialState?.user_profile || {})
    .filter(([, content]) => hasContent(content))
    .map(([label, content]) => ({ label, content }));
  const factEntries = timelineFacts(initialState?.Timeline ?? initialState?.timeline);
  return (
    <div className="conversation-context-references">
      <p className="conversation-context-note">先展示本轮已注入的上下文；“回答命中”仅在回复中可核对到对应内容时标记，不把注入误报为引用。</p>
      <section>
        <header><Typography.Text strong>用户档案</Typography.Text><span>已注入 {profileEntries.length} 项 · 回答命中 {profileCount} 项</span></header>
        <InjectedRows entries={profileEntries} emptyText="该 Case 未配置用户档案" />
        {profileEntries.length > 0 && <ReferenceRows references={references} kind="profile" />}
      </section>
      <section>
        <header><Typography.Text strong>过往事实</Typography.Text><span>已注入 {factEntries.length} 条 · 回答命中 {factCount} 条</span></header>
        <InjectedRows entries={factEntries} emptyText="该 Case 未配置过往事实" />
        {factEntries.length > 0 && <ReferenceRows references={references} kind="fact" />}
      </section>
    </div>
  );
}
