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
  return (
    <div className="runs-attribution-chart-canvas">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 42, bottom: 4, left: 4 }}
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
            width={showParent ? 184 : 156}
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
            radius={[0, 5, 5, 0]}
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
  );
}

function CategoryChartCard({
  title,
  description,
  children,
  empty,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
  empty: boolean;
}) {
  return (
    <div className="runs-attribution-category-card">
      <div className="runs-attribution-category-card__head">
        <div className="runs-attribution-category-card__title">{title}</div>
        <div className="runs-attribution-category-card__description">{description}</div>
      </div>
      {empty ? (
        <div className="runs-chart-empty">本次评测无相关数据</div>
      ) : (
        children
      )}
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
      <section className="runs-attribution-panel" aria-label="归因问题分类">
        <div className="runs-attribution-panel__head">
          <div className="runs-attribution-panel__title">归因问题分类</div>
        </div>
        <div className="runs-chart-empty"><Spin /></div>
      </section>
    );
  }

  return (
    <section className="runs-attribution-panel" aria-label="归因问题分类">
      <div className="runs-attribution-panel__head">
        <div>
          <div className="runs-attribution-panel__title">归因问题分类</div>
          <div className="runs-attribution-panel__description">
            每个 Case 仅采用最新一次成功归因，同一 Case 在同一分类下只统计一次
          </div>
        </div>
        <div className="runs-attribution-panel__count">
          已归因 <strong>{stats?.attributed_case_count || 0}</strong> 个 Case
        </div>
      </div>
      <div className="runs-attribution-category-grid">
        <CategoryChartCard
          title="归因一级分类"
          description="问题所属的核心优化方向"
          empty={firstLevel.length === 0}
        >
          <CategoryBarChart data={firstLevel} color={D.purple} />
        </CategoryChartCard>
        <CategoryChartCard
          title="归因二级分类"
          description="可直接定位和处理的具体问题"
          empty={secondLevel.length === 0}
        >
          <CategoryBarChart data={secondLevel} color={D.teal} showParent />
        </CategoryChartCard>
      </div>
    </section>
  );
}
