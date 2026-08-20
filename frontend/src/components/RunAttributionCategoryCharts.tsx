import { Spin } from "antd";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
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
  selectedKey,
  onSelect,
}: {
  data: AttributionCategoryCount[];
  color: string;
  showParent?: boolean;
  selectedKey?: string | null;
  onSelect?: (key: string) => void;
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
            labelFormatter={(label, payload) => {
              const row = payload?.[0]?.payload as AttributionCategoryCount | undefined;
              const text = String(label ?? "");
              return showParent && row?.parent_label
                ? `${row.parent_label} / ${text}`
                : text;
            }}
            formatter={(value) => [`${Number(value)} 个 Case`, "去重数量"]}
          />
          <Bar
            dataKey="case_count"
            name="Case 数量"
            fill={color}
            radius={[0, 5, 5, 0]}
            maxBarSize={20}
          >
            {data.map((row) => (
              <Cell
                key={row.key}
                fill={!selectedKey || selectedKey === row.key ? color : D.border}
                cursor={onSelect ? "pointer" : undefined}
                onClick={onSelect ? () => onSelect(row.key) : undefined}
              />
            ))}
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

export function filterSecondLevelCategories(
  rows: AttributionCategoryCount[],
  parentKey: string | null,
): AttributionCategoryCount[] {
  return parentKey ? rows.filter((row) => row.parent_key === parentKey) : rows;
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
  const [selectedFirstLevel, setSelectedFirstLevel] = useState<string | null>(null);
  const firstLevel = stats?.first_level || [];
  const secondLevel = useMemo(() => stats?.second_level || [], [stats?.second_level]);
  const effectiveSelectedKey = firstLevel.some((row) => row.key === selectedFirstLevel)
    ? selectedFirstLevel
    : null;
  const selectedFirstLevelLabel = firstLevel.find(
    (row) => row.key === effectiveSelectedKey,
  )?.label;
  const visibleSecondLevel = useMemo(
    () => filterSecondLevelCategories(secondLevel, effectiveSelectedKey),
    [secondLevel, effectiveSelectedKey],
  );
  const toggleFirstLevel = (key: string) => {
    setSelectedFirstLevel((current) => current === key ? null : key);
  };

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
          description="点击柱形筛选右侧二级分类，再次点击可取消"
          empty={firstLevel.length === 0}
        >
          <CategoryBarChart
            data={firstLevel}
            color={D.purple}
            selectedKey={effectiveSelectedKey}
            onSelect={toggleFirstLevel}
          />
        </CategoryChartCard>
        <CategoryChartCard
          title="归因二级分类"
          description={selectedFirstLevelLabel
            ? `仅展示“${selectedFirstLevelLabel}”下的具体问题`
            : "可直接定位和处理的具体问题"}
          empty={visibleSecondLevel.length === 0}
        >
          <CategoryBarChart data={visibleSecondLevel} color={D.teal} showParent />
        </CategoryChartCard>
      </div>
    </section>
  );
}
