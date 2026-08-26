import { lazy, Suspense, useEffect, useRef, useState } from "react";
import type { RunSummary } from "../api/types";
import { useLatestAttributionCategoryStats } from "../hooks/useLatestAttributionCategoryStats";

const RunAttributionCategoryCharts = lazy(() =>
  import("./RunAttributionCategoryCharts").then((module) => ({
    default: module.RunAttributionCategoryCharts,
  })),
);

/**
 * 归因分类图不影响用户先查看评测任务和核心指标。
 * 滚动到可见区域后才请求统计并加载图表依赖，避免历史归因数据增长拖慢列表首屏。
 */
export function DeferredRunAttributionCategoryCharts({ runs }: { runs: RunSummary[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const { stats, loading } = useLatestAttributionCategoryStats(runs, visible);

  useEffect(() => {
    const target = containerRef.current;
    if (!target || visible) return undefined;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "320px 0px" },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [visible]);

  return (
    <div ref={containerRef}>
      {visible ? (
        <Suspense
          fallback={(
            <div className="runs-chart-card runs-chart-card--deferred">
              <div className="runs-chart-card__title">归因问题分类</div>
              <div className="runs-chart-empty">正在加载归因分类统计…</div>
            </div>
          )}
        >
          <RunAttributionCategoryCharts
            stats={stats}
            loading={loading}
            description="仅汇总两个 Benchmark 各自最新一次成功归因；同一 Benchmark 内同一 Case 在同一分类下只统计一次"
            emptyText="两个 Benchmark 的最新归因结果暂无分类数据"
          />
        </Suspense>
      ) : (
        <div className="runs-chart-card runs-chart-card--deferred">
          <div className="runs-chart-card__title">归因问题分类</div>
          <div className="runs-chart-empty">滚动到此处后加载归因分类统计</div>
        </div>
      )}
    </div>
  );
}
