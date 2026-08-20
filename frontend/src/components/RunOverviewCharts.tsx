import { Empty } from "antd";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { palette, dashboardPieColors } from "../theme";
import { RunsChartCard } from "./RunsChartCard";

const D = palette.dashboard;
const AXIS_TICK = { fill: D.textMuted, fontSize: 11 } as const;

export function RunOverviewCharts({
  caseTypeData,
  levelData,
  dimData,
  tagData,
}: {
  caseTypeData: Array<{
    name: string;
    total: number;
    passed: number;
    failed: number;
    ratePct: number;
  }>;
  levelData: Array<{ name: string; count: number; ratePct: number }>;
  dimData: Array<{ name: string; value: number }>;
  tagData: Array<{ name: string; value: number }>;
}) {
  const categoryChartWidth = Math.max(720, caseTypeData.length * 112);

  return (
    <>
      <RunsChartCard
        title="按类别：成功 / 失败 / 通过率"
        empty={caseTypeData.length === 0}
      >
        <div className="runs-category-chart-scroll">
          <div
            className="runs-category-chart-canvas"
            style={{ width: categoryChartWidth }}
          >
            <ResponsiveContainer width="100%" height={272}>
              <ComposedChart
                data={caseTypeData}
                margin={{ top: 8, right: 14, bottom: 8, left: -6 }}
              >
                <CartesianGrid stroke={D.border} vertical={false} />
                <XAxis
                  dataKey="name"
                  axisLine={false}
                  tickLine={false}
                  interval={0}
                  height={48}
                  tick={AXIS_TICK}
                  tickFormatter={(value: string) =>
                    value.length > 8 ? `${value.slice(0, 8)}…` : value
                  }
                />
                <YAxis
                  yAxisId="count"
                  allowDecimals={false}
                  axisLine={false}
                  tickLine={false}
                  tick={AXIS_TICK}
                />
                <YAxis
                  yAxisId="rate"
                  orientation="right"
                  domain={[0, 100]}
                  unit="%"
                  axisLine={false}
                  tickLine={false}
                  tick={AXIS_TICK}
                />
                <RTooltip
                  labelFormatter={(label) => `类别：${String(label ?? "")}`}
                  formatter={(value, name) => [
                    String(name) === "通过率" ? `${Number(value)}%` : `${Number(value)} 例`,
                    String(name),
                  ]}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                <Bar
                  yAxisId="count"
                  dataKey="passed"
                  name="成功数"
                  fill={D.teal}
                  radius={[4, 4, 0, 0]}
                  maxBarSize={28}
                />
                <Bar
                  yAxisId="count"
                  dataKey="failed"
                  name="失败数"
                  fill={D.red}
                  radius={[4, 4, 0, 0]}
                  maxBarSize={28}
                />
                <Line
                  yAxisId="rate"
                  type="monotone"
                  dataKey="ratePct"
                  name="通过率"
                  stroke={D.purple}
                  strokeWidth={2}
                  dot={{ r: 3, fill: D.card, stroke: D.purple, strokeWidth: 2 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      </RunsChartCard>

      <div className="runs-duo-charts runs-duo-charts--trio">
        <RunsChartCard title="分层级：数量 / 通过率">
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart
              data={levelData}
              margin={{ top: 8, right: 8, bottom: 0, left: -10 }}
            >
              <CartesianGrid stroke={D.border} vertical={false} />
              <XAxis
                dataKey="name"
                axisLine={false}
                tickLine={false}
                tick={AXIS_TICK}
              />
              <YAxis
                yAxisId="count"
                allowDecimals={false}
                axisLine={false}
                tickLine={false}
                tick={AXIS_TICK}
              />
              <YAxis
                yAxisId="rate"
                orientation="right"
                domain={[0, 100]}
                unit="%"
                axisLine={false}
                tickLine={false}
                tick={AXIS_TICK}
              />
              <RTooltip
                formatter={(value, name) =>
                  String(name) === "通过率" ? `${Number(value)}%` : Number(value)
                }
              />
              <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
              <Bar
                yAxisId="count"
                dataKey="count"
                name="用例数"
                fill={D.purple}
                radius={[4, 4, 0, 0]}
                maxBarSize={28}
              />
              <Line
                yAxisId="rate"
                type="monotone"
                dataKey="ratePct"
                name="通过率"
                stroke={D.teal}
                strokeWidth={2}
                dot={{ r: 3, fill: D.card, stroke: D.teal, strokeWidth: 2 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </RunsChartCard>

        <RunsChartCard title="八维平均分">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={dimData}
              margin={{ top: 8, right: 8, bottom: 0, left: -12 }}
            >
              <CartesianGrid stroke={D.border} vertical={false} />
              <XAxis
                dataKey="name"
                axisLine={false}
                tickLine={false}
                tick={AXIS_TICK}
              />
              <YAxis
                domain={[0, 5]}
                ticks={[0, 1, 2, 3, 4, 5]}
                allowDataOverflow
                axisLine={false}
                tickLine={false}
                tick={AXIS_TICK}
              />
              <RTooltip
                formatter={(value) => [
                  `${Number(value).toFixed(2)} / 5`,
                  "平均分",
                ]}
              />
              <Bar
                dataKey="value"
                name="平均分"
                radius={[4, 4, 0, 0]}
                maxBarSize={36}
              >
                {dimData.map((_, i) => (
                  <Cell key={i} fill={i % 2 ? D.purpleLine : D.purple} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </RunsChartCard>

        <RunsChartCard title="失败标签分布">
          {tagData.length === 0 ? (
            <div className="runs-chart-empty">
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="无失败标签"
              />
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={tagData}
                  dataKey="value"
                  nameKey="name"
                  cx="42%"
                  cy="50%"
                  innerRadius={48}
                  outerRadius={72}
                  paddingAngle={2}
                >
                  {tagData.map((_, i) => (
                    <Cell
                      key={i}
                      fill={dashboardPieColors[i % dashboardPieColors.length]}
                    />
                  ))}
                </Pie>
                <RTooltip
                  formatter={(value, name) => [`${Number(value)} 例`, String(name)]}
                />
                <Legend
                  layout="vertical"
                  align="right"
                  verticalAlign="middle"
                  iconType="circle"
                  wrapperStyle={{ fontSize: 12 }}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </RunsChartCard>
      </div>
    </>
  );
}
