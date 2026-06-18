import type { ReactNode } from "react";

/** 看板图表 / 指标卡共用外壳（`.runs-chart-card`）。 */
export function RunsChartCard({
  title,
  children,
  empty,
  metric,
}: {
  title: string;
  children: ReactNode;
  empty?: boolean;
  /** 延迟/Token 指标卡附加 class */
  metric?: boolean;
}) {
  return (
    <div className={`runs-chart-card${metric ? " runs-metric-card" : ""}`}>
      <div className="runs-chart-card__title runs-chart-card__title--solo">{title}</div>
      {empty ? (
        <div className="runs-chart-empty runs-chart-empty--compact">本次评测无相关数据</div>
      ) : metric ? (
        children
      ) : (
        <div className="runs-chart-area runs-chart-area--short">{children}</div>
      )}
    </div>
  );
}
