export interface OnlineEvalConversationSource {
  raw_messages?: unknown;
  user_text?: unknown;
  assistant_text?: unknown;
}

export interface OnlineEvalConversationMessage {
  role: string;
  content: string;
}

export interface OnlineEvalConversationRound {
  user?: string;
  assistant?: string;
  extras: OnlineEvalConversationMessage[];
}

function textValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : String(value ?? "").trim();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function appendText(current: string | undefined, content: string) {
  return current ? `${current}\n\n${content}` : content;
}

export function normaliseOnlineEvalMessages(
  source: OnlineEvalConversationSource
): OnlineEvalConversationMessage[] {
  if (Array.isArray(source.raw_messages)) {
    const messages = source.raw_messages
      .filter(isRecord)
      .map((message) => ({
        role: textValue(message.role).toLowerCase(),
        content: textValue(message.content),
      }))
      .filter((message) => message.content);
    if (messages.length) return messages;
  }

  const fallback: OnlineEvalConversationMessage[] = [];
  const userText = textValue(source.user_text);
  const assistantText = textValue(source.assistant_text);
  if (userText) fallback.push({ role: "user", content: userText });
  if (assistantText) fallback.push({ role: "assistant", content: assistantText });
  return fallback;
}

export function buildOnlineEvalConversationRounds(
  source: OnlineEvalConversationSource
): OnlineEvalConversationRound[] {
  const rounds: OnlineEvalConversationRound[] = [];

  normaliseOnlineEvalMessages(source).forEach((message) => {
    if (message.role === "user" || rounds.length === 0) {
      rounds.push({ extras: [] });
    }
    const current = rounds[rounds.length - 1];
    if (message.role === "user") {
      current.user = appendText(current.user, message.content);
    } else if (message.role === "assistant") {
      current.assistant = appendText(current.assistant, message.content);
    } else {
      current.extras.push(message);
    }
  });

  return rounds.filter((round) => round.user || round.assistant || round.extras.length);
}

export function onlineEvalRoleLabel(role: string) {
  if (role === "user") return "用户问题";
  if (role === "assistant") return "Cx 回复";
  if (role === "system") return "系统消息";
  return role || "其他消息";
}
