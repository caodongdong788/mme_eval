import { useEffect, useState } from "react";
import { api } from "./api";

// 模块级缓存：失败标签中文映射全应用只拉一次。
let cache: Record<string, string> | null = null;
let inflight: Promise<Record<string, string>> | null = null;

function load(): Promise<Record<string, string>> {
  if (cache) return Promise.resolve(cache);
  if (!inflight) {
    inflight = api
      .getFailureTagLabels()
      .then((m) => {
        cache = m;
        return m;
      })
      .catch(() => ({}));
  }
  return inflight;
}

/** 失败标签英文枚举值 → 中文短标签；未知值回退原值。 */
export function useFailureTagLabels(): (tag: string) => string {
  const [labels, setLabels] = useState<Record<string, string>>(cache || {});
  useEffect(() => {
    let alive = true;
    load().then((m) => alive && setLabels(m));
    return () => {
      alive = false;
    };
  }, []);
  return (tag: string) => labels[tag] || tag;
}
