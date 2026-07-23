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

// 失败标签属于固定平台枚举。先提供前端默认值，避免配置接口尚未返回或浏览器
// 缓存旧映射时，把内部枚举值（如 medical_safety_risk）直接暴露给用户。
const DEFAULT_FAILURE_TAG_LABELS: Record<string, string> = {
  adapter_error: "Agent 调用失败",
  medical_safety_risk: "医学安全风险",
  professional_accuracy_gap: "医学准确性不足",
  clinical_inquiry_gap: "关键追问不足",
  personalization_gap: "用户档案未使用",
  guideline_coverage_low: "指南覆盖不足",
  score_below_threshold: "总分未达标",
};

const fetchFailureTagLabels = () => api.getFailureTagLabels();
const fetchJudgeVerdictLabels = () => api.getJudgeVerdictLabels();

/** 失败标签英文枚举值 → 中文短标签；未知值回退原值。 */
export function useFailureTagLabels(): (tag: string) => string {
  return useConfigLabelMap(
    CACHE_KEY_FAILURE,
    fetchFailureTagLabels,
    (labels, tag) => labels[tag] || DEFAULT_FAILURE_TAG_LABELS[tag] || tag
  );
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
