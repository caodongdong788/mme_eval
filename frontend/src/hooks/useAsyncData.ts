import { useCallback, useEffect, useRef, useState } from "react";
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
  fallbackMessage = "加载失败",
  options: { enabled?: boolean } = {},
): AsyncData<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);
  const enabled = options.enabled ?? true;

  const run = useCallback(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    const requestGeneration = ++generation.current;
    setLoading(true);
    setError(null);
    fetcher()
      .then((res) => {
        if (generation.current === requestGeneration) setData(res);
      })
      .catch((e) => {
        if (generation.current === requestGeneration) {
          setError(formatApiError(e, fallbackMessage));
        }
      })
      .finally(() => {
        if (generation.current === requestGeneration) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, ...deps]);

  useEffect(() => {
    run();
    return () => {
      generation.current += 1;
    };
  }, [run]);

  return { data, loading, error, reload: run };
}
