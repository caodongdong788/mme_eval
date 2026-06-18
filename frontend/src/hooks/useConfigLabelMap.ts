import { useEffect, useState } from "react";
import { api } from "../api/index";

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

const CACHE_KEY_FAILURE = "failure-tags";
const CACHE_KEY_JUDGE = "judge-verdict";

const fetchFailureTagLabels = () => api.getFailureTagLabels();
const fetchJudgeVerdictLabels = () => api.getJudgeVerdictLabels();

/** 失败标签英文枚举值 → 中文短标签；未知值回退原值。 */
export function useFailureTagLabels(): (tag: string) => string {
  return useConfigLabelMap(CACHE_KEY_FAILURE, fetchFailureTagLabels, (labels, tag) => labels[tag] || tag);
}

/** Judge verdict 全名 → 中文标签；未知值回退英文名。 */
export function useJudgeVerdictLabels(): (name: string | undefined) => string {
  const resolve = useConfigLabelMap(
    CACHE_KEY_JUDGE,
    fetchJudgeVerdictLabels,
    (labels, name) => labels[name] || name
  );
  return (name: string | undefined) => (name ? resolve(name) : "-");
}
