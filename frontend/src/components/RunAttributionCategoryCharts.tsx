import { Spin } from "antd";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  AttributionCategoryCount,
  RunAttributionCategoryStats,
} from "../api";
import { palette } from "../theme";
import { RunsChartCard } from "./RunsChartCard";

const D = palette.dashboard;
const AXIS_TICK = { fill: D.textMuted, fontSize: 11 } as const;

function CategoryBarChart({
  data,
  color,
  showParent,
}: {
  data: AttributionCategoryCount[];
  color: string;
  showParent?: boolean;
}) {
  const height = Math.max(220, data.length * 36 + 28);
  return (
    <div className="runs-attribution-chart-scroll">
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 6, right: 42, bottom: 4, left: 4 }}
          >
            <CartesianGrid stroke={D.border} horizontal={false} />
            <XAxis
              type="number"
              allowDecimals={false}
              axisLine={false}
              tickLine={false}
              tick={AXIS_TICK}
            />
            <YAxis
              type="category"
              dataKey="label"
              width={showParent ? 184 : 142}
              axisLine={false}
              tickLine={false}
              tick={AXIS_TICK}
              interval={0}
            />
            <RTooltip
              labelFormatter={(label: string, payload) => {
                const row = payload?.[0]?.payload as AttributionCategoryCount | undefined;
                return showParent && row?.parent_label
                  ? `${row.parent_label} / ${label}`
                  : label;
              }}
              formatter={(value: number) => [`${value} 个 Case`, "去重数量"]}
            />
            <Bar
              dataKey="case_count"
              name="Case 数量"
              fill={color}
              radius={[0, 4, 4, 0]}
              maxBarSize={20}
            >
              <LabelList
                dataKey="case_count"
                position="right"
                fill={D.text}
                fontSize={11}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function RunAttributionCategoryCharts({
  stats,
  loading,
}: {
  stats: RunAttributionCategoryStats | null;
  loading: boolean;
}) {
  const firstLevel = stats?.first_level || [];
  const secondLevel = stats?.second_level || [];

  if (loading) {
    return (
      <RunsChartCard title="归因问题分类（按 Case 去重）">
        <div className="runs-chart-empty"><Spin /></div>
      </RunsChartCard>
    );
  }

  return (
    <section aria-label="归因问题分类">
      <div className="runs-attribution-chart-summary">
        每个 Case 仅采用最新一次成功归因；同一 Case 在同一分类下只统计一次
        {stats?.attributed_case_count ? ` · 已归因 ${stats.attributed_case_count} 个 Case` : ""}
      </div>
      <div className="runs-duo-charts runs-attribution-category-charts">
        <RunsChartCard
          title="归因一级分类"
          empty={firstLevel.length === 0}
        >
          <CategoryBarChart data={firstLevel} color={D.purple} />
        </RunsChartCard>
        <RunsChartCard
          title="归因二级分类"
          empty={secondLevel.length === 0}
        >
          <CategoryBarChart data={secondLevel} color={D.teal} showParent />
        </RunsChartCard>
      </div>
    </section>
  );
}
