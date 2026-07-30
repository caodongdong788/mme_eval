import { useEffect, useState } from "react";
import { api } from "../api/index";
import type { ConversationMessage } from "../components/ConversationThread";

export interface PairwiseConversationReplay {
  messages: ConversationMessage[];
  /** cx-agent 生成的原生回放页；存在时优先嵌入，避免两套对话样式不一致。 */
  replayUrl?: string;
}

const cache = new Map<string, PairwiseConversationReplay>();

function cacheKey(runId: number, sampleId: string) {
  return `${runId}:${sampleId}`;
}

async function fetchMessages(runId: number, sampleId: string): Promise<PairwiseConversationReplay> {
  const key = cacheKey(runId, sampleId);
  const hit = cache.get(key);
  if (hit) return hit;
  try {
    const d = await api.getCaseDetail(runId, sampleId);
    const traceMessages = d?.trace?.messages || [];
    const caseUserTurns = (d?.case?.turns || []).filter((turn: { role?: string }) => turn.role === "user");
    let userTurnIndex = 0;
    const messages = traceMessages.map((message: ConversationMessage) => {
      if (message.role !== "user") return message;
      const images = caseUserTurns[userTurnIndex++]?.images || [];
      return images.length ? { ...message, images } : message;
    });
    const replay = {
      messages,
      replayUrl: d?.trace?.cx_evaluation_share_url || undefined,
    };
    cache.set(key, replay);
    return replay;
  } catch {
    return { messages: [] };
  }
}

/** 清除模块级缓存（单测用）。 */
export function clearPairwiseMessagesCache() {
  cache.clear();
}

/** Pairwise 展开行：并行拉取 A/B 对话，模块级缓存避免重复请求。 */
export function usePairwiseExpandedMessages(runAId: number, runBId: number, sampleId: string) {
  const [conversationA, setConversationA] = useState<PairwiseConversationReplay>(
    () => cache.get(cacheKey(runAId, sampleId)) || { messages: [] }
  );
  const [conversationB, setConversationB] = useState<PairwiseConversationReplay>(
    () => cache.get(cacheKey(runBId, sampleId)) || { messages: [] }
  );

  useEffect(() => {
    if (!sampleId) {
      setConversationA({ messages: [] });
      setConversationB({ messages: [] });
      return;
    }
    let cancelled = false;
    Promise.all([fetchMessages(runAId, sampleId), fetchMessages(runBId, sampleId)]).then(
      ([a, b]) => {
        if (!cancelled) {
          setConversationA(a);
          setConversationB(b);
        }
      }
    );
    return () => {
      cancelled = true;
    };
  }, [runAId, runBId, sampleId]);

  return {
    messagesA: conversationA.messages,
    messagesB: conversationB.messages,
    replayUrlA: conversationA.replayUrl,
    replayUrlB: conversationB.replayUrl,
  };
}
