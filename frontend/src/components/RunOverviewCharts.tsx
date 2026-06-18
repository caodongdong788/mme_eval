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
  levelData,
  dimData,
  tagData,
}: {
  levelData: Array<{ name: string; count: number; ratePct: number }>;
  dimData: Array<{ name: string; value: number }>;
  tagData: Array<{ name: string; value: number }>;
}) {
  return (
    <div className="runs-duo-charts runs-duo-charts--trio">
      <RunsChartCard title="分层级：数量 / 通过率">
        <ResponsiveContainer width="100%" height={220}>
          <ComposedChart data={levelData} margin={{ top: 8, right: 8, bottom: 0, left: -10 }}>
            <CartesianGrid stroke={D.border} vertical={false} />
            <XAxis dataKey="name" axisLine={false} tickLine={false} tick={AXIS_TICK} />
            <YAxis yAxisId="count" allowDecimals={false} axisLine={false} tickLine={false} tick={AXIS_TICK} />
            <YAxis
              yAxisId="rate"
              orientation="right"
              domain={[0, 100]}
              unit="%"
              axisLine={false}
              tickLine={false}
              tick={AXIS_TICK}
            />
            <RTooltip formatter={(v: number, name: string) => (name === "通过率" ? `${v}%` : v)} />
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

      <RunsChartCard title="四模块平均分">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={dimData} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid stroke={D.border} vertical={false} />
            <XAxis dataKey="name" axisLine={false} tickLine={false} tick={AXIS_TICK} />
            <YAxis axisLine={false} tickLine={false} tick={AXIS_TICK} />
            <RTooltip />
            <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={36}>
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
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无失败标签" />
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
                  <Cell key={i} fill={dashboardPieColors[i % dashboardPieColors.length]} />
                ))}
              </Pie>
              <RTooltip formatter={(v: number, n: string) => [`${v} 例`, n]} />
              <Legend layout="vertical" align="right" verticalAlign="middle" iconType="circle" wrapperStyle={{ fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        )}
      </RunsChartCard>
    </div>
  );
}
