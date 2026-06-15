import { useCallback, useEffect, useState } from "react";
import { formatApiError } from "../utils/apiError";

export interface AsyncData<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

// 统一的异步取数 hook：集中管理 loading / error / reload，避免各页重复写
// useState + useEffect + try/catch，并消除「请求失败后永久 loading」。
export function useAsyncData<T>(
  fetcher: () => Promise<T>,
  deps: unknown[],
  fallbackMessage = "加载失败"
): AsyncData<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetcher()
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e) => {
        if (!cancelled) setError(formatApiError(e, fallbackMessage));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => run(), [run]);

  return { data, loading, error, reload: run };
}
