import { Empty } from "antd";
import { useEffect, useRef, useState } from "react";
import { ConversationThread, type ConversationMessage } from "./ConversationThread";

const REPLAY_READY_EVENT = "cx-evaluation-replay-ready";
const REPLAY_READY_TIMEOUT_MS = 4_000;

interface CxReplayEmbedProps {
  src?: string | null;
  messages: ConversationMessage[];
  resolveImageSrc?: (imagePath: string) => string;
  onFallbackChange?: (fallback: boolean) => void;
}

/**
 * CX 分享页在真正渲染对话后通过 postMessage 回执。未收到回执通常意味着 iframe
 * 被 CSP 拦截或分享页不可用，此时自动回退为 MME 已存的对话，避免留下灰色空白框。
 */
export function CxReplayEmbed({ src, messages, resolveImageSrc, onFallbackChange }: CxReplayEmbedProps) {
  const [fallback, setFallback] = useState(false);
  const onFallbackChangeRef = useRef(onFallbackChange);

  useEffect(() => {
    onFallbackChangeRef.current = onFallbackChange;
  }, [onFallbackChange]);

  const updateFallback = (nextFallback: boolean) => {
    setFallback(nextFallback);
    onFallbackChangeRef.current?.(nextFallback);
  };

  useEffect(() => {
    updateFallback(false);
    if (!src) return undefined;
    let origin = "";
    try {
      origin = new URL(src).origin;
    } catch {
      updateFallback(true);
      return undefined;
    }

    const onMessage = (event: MessageEvent) => {
      if (
        event.origin === origin
        && event.data?.source === "cx-agent"
        && event.data?.type === REPLAY_READY_EVENT
      ) {
        window.clearTimeout(timeout);
      }
    };
    const timeout = window.setTimeout(() => updateFallback(true), REPLAY_READY_TIMEOUT_MS);
    window.addEventListener("message", onMessage);
    return () => {
      window.clearTimeout(timeout);
      window.removeEventListener("message", onMessage);
    };
  }, [src]);

  if (!src) {
    return messages.length ? (
      <ConversationThread messages={messages} maxHeight={640} resolveImageSrc={resolveImageSrc} />
    ) : (
      <Empty description="此用例没有可用的对话内容" />
    );
  }

  if (fallback) {
    return (
      <div>
        {messages.length ? (
          <ConversationThread messages={messages} maxHeight={640} resolveImageSrc={resolveImageSrc} />
        ) : (
          <Empty description="此用例没有可用的本地回放内容，请在新窗口打开 CX 原生回放" />
        )}
      </div>
    );
  }

  return (
    <iframe
      title="CX 完整回放"
      src={src}
      onError={() => updateFallback(true)}
      style={{ display: "block", width: "100%", height: 640, border: 0, borderRadius: 8 }}
    />
  );
}
