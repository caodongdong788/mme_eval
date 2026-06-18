import { InfoCircleOutlined } from "@ant-design/icons";
import { Tooltip } from "antd";
import type { ReactNode } from "react";

export const PERIOD_COMPARE_TIP =
  "较上周期变化：上周期为与所选日期等长的紧邻上一段时间（按创建时间统计）";

/** 评测列表 / 看板 / Pairwise 共用的 KPI 瓦片（`.runs-kpi`）。 */
export function RunsKpi({
  title,
  tip,
  value,
  unit,
  sub,
  trend,
  danger,
  valueStyle,
}: {
  title: string;
  tip?: string;
  value: ReactNode;
  unit?: string;
  sub?: ReactNode;
  trend?: ReactNode;
  danger?: boolean;
  valueStyle?: React.CSSProperties;
}) {
  return (
    <div className={`runs-kpi${danger ? " runs-kpi--danger" : ""}`}>
      <div className="runs-kpi__title">
        {title}
        {tip && (
          <Tooltip title={tip}>
            <InfoCircleOutlined className="runs-kpi__info" />
          </Tooltip>
        )}
      </div>
      <div className="runs-kpi__value-row">
        <span className="runs-kpi__value" style={valueStyle}>
          {value}
        </span>
        {unit && <span className="runs-kpi__unit">{unit}</span>}
      </div>
      {sub != null && <div className="runs-kpi__sub">{sub}</div>}
      {trend}
    </div>
  );
}

export function PeriodDeltaBadge({
  delta,
  unit,
  invertColor,
  percent,
}: {
  delta: number | null;
  unit?: string;
  invertColor?: boolean;
  /** 为 true 时 delta 已是百分点，展示时不乘 100 */
  percent?: boolean;
}) {
  if (delta == null) return null;
  if (delta === 0) {
    return <span className="runs-kpi__trend runs-kpi__trend--neutral">较上周期 持平</span>;
  }
  const up = delta > 0;
  const good = invertColor ? !up : up;
  const suffix = unit ?? (percent ? "%" : "");
  return (
    <Tooltip title={PERIOD_COMPARE_TIP}>
      <span className={`runs-kpi__trend ${good ? "runs-kpi__trend--up" : "runs-kpi__trend--down"}`}>
        较上周期 {up ? "↑" : "↓"} {Math.abs(delta)}
        {suffix}
      </span>
    </Tooltip>
  );
}
