import { type ReactNode } from "react";

// KPI 瓦片：Caption 标签 + Mono 大数字（样式见 styles.css .kpi-tile/.kpi-value）。
export function KpiTile({
  label,
  value,
  sub,
  emphasize,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  emphasize?: boolean;
}) {
  return (
    <div className="kpi-tile">
      <div className="kpi-label">{label}</div>
      <div className={emphasize ? "kpi-value is-fail" : "kpi-value"}>{value}</div>
      {sub != null && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}
