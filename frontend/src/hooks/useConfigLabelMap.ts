import { useEffect, useState } from "react";

const caches = new Map<string, Record<string, string>>();
const inflights = new Map<string, Promise<Record<string, string>>>();

function loadCached(
  cacheKey: string,
  fetcher: () => Promise<Record<string, string>>
): Promise<Record<string, string>> {
  const hit = caches.get(cacheKey);
  if (hit) return Promise.resolve(hit);
  let p = inflights.get(cacheKey);
  if (!p) {
    p = fetcher()
      .then((m) => {
        caches.set(cacheKey, m);
        return m;
      })
      .catch(() => ({}));
    inflights.set(cacheKey, p);
  }
  return p;
}

/** 清除模块级缓存（单测用）。 */
export function clearConfigLabelMapCache(cacheKey?: string) {
  if (cacheKey) {
    caches.delete(cacheKey);
    inflights.delete(cacheKey);
  } else {
    caches.clear();
    inflights.clear();
  }
}

/**
 * 配置类标签映射：模块级缓存 + 组件内 state，全应用每种 key 只拉一次。
 */
export function useConfigLabelMap(
  cacheKey: string,
  fetcher: () => Promise<Record<string, string>>,
  resolve: (labels: Record<string, string>, key: string) => string
): (key: string) => string {
  const [labels, setLabels] = useState<Record<string, string>>(() => caches.get(cacheKey) || {});
  useEffect(() => {
    let alive = true;
    loadCached(cacheKey, fetcher).then((m) => alive && setLabels(m));
    return () => {
      alive = false;
    };
  }, [cacheKey, fetcher]);
  return (key: string) => resolve(labels, key);
}
