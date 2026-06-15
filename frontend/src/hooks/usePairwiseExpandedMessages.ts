import { useEffect, useState } from "react";
import { api } from "../api/index";
import type { ConversationMessage } from "../components/ConversationThread";

const cache = new Map<string, ConversationMessage[]>();

function cacheKey(runId: number, sampleId: string) {
  return `${runId}:${sampleId}`;
}

async function fetchMessages(runId: number, sampleId: string): Promise<ConversationMessage[]> {
  const key = cacheKey(runId, sampleId);
  const hit = cache.get(key);
  if (hit) return hit;
  try {
    const d = await api.getCaseDetail(runId, sampleId);
    const messages = d?.trace?.messages || [];
    cache.set(key, messages);
    return messages;
  } catch {
    return [];
  }
}

/** 清除模块级缓存（单测用）。 */
export function clearPairwiseMessagesCache() {
  cache.clear();
}

/** Pairwise 展开行：并行拉取 A/B 对话，模块级缓存避免重复请求。 */
export function usePairwiseExpandedMessages(runAId: number, runBId: number, sampleId: string) {
  const [messagesA, setMessagesA] = useState<ConversationMessage[]>(
    () => cache.get(cacheKey(runAId, sampleId)) || []
  );
  const [messagesB, setMessagesB] = useState<ConversationMessage[]>(
    () => cache.get(cacheKey(runBId, sampleId)) || []
  );

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchMessages(runAId, sampleId), fetchMessages(runBId, sampleId)]).then(
      ([a, b]) => {
        if (!cancelled) {
          setMessagesA(a);
          setMessagesB(b);
        }
      }
    );
    return () => {
      cancelled = true;
    };
  }, [runAId, runBId, sampleId]);

  return { messagesA, messagesB };
}
