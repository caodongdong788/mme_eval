import { parseProfileMemoryEntry } from "../profileMemory";

export type ContextKind = "profile" | "fact";

export interface ConversationContextInitialState {
  user_profile?: Record<string, unknown>;
  Timeline?: unknown;
  timeline?: unknown;
  profile_memory?: unknown[];
  response_preferences?: unknown[];
  medical_documents?: unknown[];
  chat_history?: unknown[];
  tool_state?: Record<string, unknown>;
}

export interface AssistantMessage {
  role: string;
  content: string;
}

export interface ContextReference {
  kind: ContextKind;
  label: string;
  content: unknown;
  turns: number[];
  evidence: string;
}

export interface InitializationModule {
  key: string;
  label: string;
  entries: Array<{ label: string; content: string; referenceKind?: ContextKind }>;
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
  return bestLength >= 6 ? a.slice(bestEnd - bestLength, bestEnd) : "";
}

function fuzzyExcerpt(left: string, right: string): string {
  const directExcerpt = longestCommonExcerpt(left, right);
  if (directExcerpt) return directExcerpt;
  const a = comparable(left);
  const b = comparable(right);
  if (a.length < 4 || b.length < 4) return "";
  const bigrams = (text: string) => new Set(
    Array.from({ length: text.length - 1 }, (_, index) => text.slice(index, index + 2)),
  );
  const sourceBigrams = bigrams(a);
  const replyBigrams = bigrams(b);
  const shared = [...sourceBigrams].filter((gram) => replyBigrams.has(gram));
  if (shared.length < 3 || shared.length / Math.min(sourceBigrams.size, replyBigrams.size) < 0.4) return "";
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

function array(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function metricText(value: unknown): string {
  const metric = record(value);
  const result = metric.value ?? metric.text_value ?? "—";
  return `${String(metric.name || "未命名指标")}：${result}${metric.unit ? ` ${metric.unit}` : ""}${metric.measured_at ? `（${metric.measured_at}）` : ""}`;
}

function preferenceText(value: unknown): string {
  const item = record(value);
  const preference = String(item.preference || "").trim();
  const basis = String(item.basis || "").trim();
  return [preference, basis ? `依据：${basis}` : ""].filter(Boolean).join("；");
}

function checkInText(value: unknown): string {
  const item = record(value);
  const labels = new Map(array(item.fields).map((field) => {
    const entry = record(field);
    return [String(entry.key || ""), String(entry.label || entry.key || "")];
  }));
  const values = Object.entries(record(item.values))
    .map(([key, content]) => `${labels.get(key) || key}：${renderValue(content)}`)
    .join("；");
  return [
    item.category_name ? `类型：${item.category_name}` : "",
    item.recorded_at ? `记录时间：${item.recorded_at}` : "",
    values,
    array(item.tags).length ? `标签：${array(item.tags).map(String).join("、")}` : "",
  ].filter(Boolean).join("；");
}

export function accountInitializationModules(
  initialState?: ConversationContextInitialState,
): InitializationModule[] {
  if (!initialState) return [];
  const modules: InitializationModule[] = [];
  const profileEntries = Object.entries(initialState.user_profile || {})
    .filter(([, content]) => hasContent(content))
    .map(([label, content]) => ({ label, content: renderValue(content), referenceKind: "profile" as const }));
  if (profileEntries.length) modules.push({ key: "user_profile", label: "用户档案", entries: profileEntries });

  const factEntries = timelineFacts(initialState.Timeline ?? initialState.timeline)
    .map((fact) => ({ label: fact.label, content: renderValue(fact.content), referenceKind: "fact" as const }));
  if (factEntries.length) modules.push({ key: "timeline", label: "过往事实", entries: factEntries });

  const memories = array(initialState.profile_memory)
    .map(parseProfileMemoryEntry)
    .filter((item) => item.content.trim())
    .map((item, index) => ({ label: item.category || `长期记忆 ${index + 1}`, content: item.content.trim() }));
  if (memories.length) modules.push({ key: "profile_memory", label: "长期画像记忆", entries: memories });

  const preferences = array(initialState.response_preferences)
    .map(preferenceText).filter(Boolean)
    .map((content, index) => ({ label: `回复偏好 ${index + 1}`, content }));
  if (preferences.length) modules.push({ key: "response_preferences", label: "回复偏好", entries: preferences });

  const documents = array(initialState.medical_documents).map(record).filter((item) => Object.keys(item).length)
    .map((document, index) => {
      const metrics = array(document.metrics).map(metricText).filter(Boolean);
      return {
        label: String(document.title || document.ref || `病例资料 ${index + 1}`),
        content: [
          document.document_date ? `日期：${document.document_date}` : "",
          document.document_type ? `资料类型：${document.document_type}` : "",
          metrics.length ? `结构化指标：${metrics.join("；")}` : "",
        ].filter(Boolean).join("；"),
      };
    });
  if (documents.length) modules.push({ key: "medical_documents", label: "病例夹", entries: documents });

  const histories = array(initialState.chat_history).map(record).filter((item) => Object.keys(item).length)
    .map((conversation, index) => ({
      label: String(conversation.title || conversation.ref || `历史对话 ${index + 1}`),
      content: [
        conversation.started_at ? `开始时间：${conversation.started_at}` : "",
        ...array(conversation.messages).map(record)
          .map((message) => `${message.role === "assistant" ? "Agent" : "用户"}：${String(message.content || "")}`),
      ].filter(Boolean).join("；"),
    }));
  if (histories.length) modules.push({ key: "chat_history", label: "历史对话", entries: histories });

  const toolState = record(initialState.tool_state);
  const scheduledTasks = array(toolState.scheduled_tasks).map(record).filter((item) => Object.keys(item).length)
    .map((task, index) => ({
      label: String(task.task_name || task.ref || `提醒任务 ${index + 1}`),
      content: [task.due_at ? `提醒时间：${task.due_at}` : "", task.message ? `内容：${task.message}` : ""].filter(Boolean).join("；"),
    }));
  if (scheduledTasks.length) modules.push({ key: "scheduled_tasks", label: "提醒任务", entries: scheduledTasks });

  const checkIns = array(toolState.check_ins).map(record).filter((item) => Object.keys(item).length)
    .map((item, index) => ({ label: String(item.title || item.ref || `打卡记录 ${index + 1}`), content: checkInText(item) }));
  if (checkIns.length) modules.push({ key: "check_ins", label: "打卡记录", entries: checkIns });

  const undercurrentTasks = array(toolState.undercurrent_tasks).map(record).filter((item) => Object.keys(item).length)
    .map((task, index) => ({
      label: String(task.ref || `暗流任务 ${index + 1}`),
      content: [
        task.kind ? `任务类型：${task.kind}` : "",
        task.status ? `状态：${task.status}` : "",
        task.next_due_at ? `下次处理：${task.next_due_at}` : "",
        hasContent(task.payload) ? `任务内容：${renderValue(task.payload)}` : "",
      ].filter(Boolean).join("；"),
    }));
  if (undercurrentTasks.length) modules.push({ key: "undercurrent_tasks", label: "暗流任务", entries: undercurrentTasks });
  return modules;
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
