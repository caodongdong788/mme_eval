import { useEffect, useRef } from "react";

interface PollingOptions {
  enabled?: boolean;
  immediate?: boolean;
  intervalMs: number;
  runWhenHidden?: boolean;
}

/**
 * 无重叠轮询：只有上一轮完成后才开始计时，并忽略卸载后的迟到响应。
 * task 返回的数据仍由调用方落 state；isCurrent 可防止旧请求覆盖新页面状态。
 */
export function usePollingTask(
  task: (isCurrent: () => boolean) => Promise<void>,
  deps: unknown[],
  {
    enabled = true,
    immediate = true,
    intervalMs,
    runWhenHidden = false,
  }: PollingOptions,
) {
  const generation = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    const currentGeneration = ++generation.current;
    let disposed = false;
    let timer: number | undefined;
    let running = false;

    const isCurrent = () =>
      !disposed && generation.current === currentGeneration;
    const schedule = () => {
      if (!isCurrent()) return;
      timer = window.setTimeout(run, intervalMs);
    };
    const run = async () => {
      if (!isCurrent() || running) return;
      if (!runWhenHidden && document.visibilityState !== "visible") {
        schedule();
        return;
      }
      running = true;
      try {
        await task(isCurrent);
      } catch {
        // 轮询失败由调用方按页面语义展示；调度器本身保持下一轮可恢复。
      } finally {
        running = false;
        schedule();
      }
    };
    const onVisibility = () => {
      if (document.visibilityState !== "visible" || running) return;
      if (timer !== undefined) window.clearTimeout(timer);
      void run();
    };

    if (immediate) void run();
    else schedule();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      disposed = true;
      generation.current += 1;
      if (timer !== undefined) window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
    // task 由显式 deps 控制，避免调用方为只供轮询使用的闭包重复包 useCallback。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, immediate, intervalMs, runWhenHidden, ...deps]);
}
