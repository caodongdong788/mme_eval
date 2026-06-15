import { Card, Empty } from "antd";
import {
  Bar,
  BarChart,
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
import { palette } from "../theme";

const PIE_COLORS = [
  palette.chart.teal,
  palette.chart.ink,
  palette.chart.muted,
  palette.chart.faint,
];

const AXIS_TICK = { fill: palette.muted, fontSize: 12 } as const;

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
    <div className="ov-trio">
      <div className="ov-col">
        <Card title="分层级：数量 / 通过率" size="small">
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={levelData} margin={{ top: 8, right: 8, bottom: 0, left: -10 }}>
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={AXIS_TICK} />
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
              <RTooltip formatter={(v: number, name: string) => (name === "通过率" ? `${v}%` : v)} />
              <Legend iconType="circle" />
              <Bar
                yAxisId="count"
                dataKey="count"
                name="用例数"
                fill={palette.chart.teal}
                radius={[3, 3, 0, 0]}
                maxBarSize={24}
              />
              <Line
                yAxisId="rate"
                type="monotone"
                dataKey="ratePct"
                name="通过率"
                stroke={palette.chart.ink}
                strokeWidth={1.5}
                dot={{ r: 2.5, fill: palette.chart.ink }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>
      </div>
      <div className="ov-col">
        <Card title="四模块平均分" size="small">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={dimData}>
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={AXIS_TICK} />
              <YAxis axisLine={false} tickLine={false} tick={AXIS_TICK} />
              <RTooltip />
              <Bar dataKey="value" fill={palette.chart.teal} radius={[3, 3, 0, 0]} maxBarSize={36} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
      <div className="ov-col">
        <Card title="失败标签分布" size="small">
          {tagData.length === 0 ? (
            <div style={{ height: 220, display: "grid", placeItems: "center" }}>
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
                  innerRadius={42}
                  outerRadius={72}
                  paddingAngle={2}
                >
                  {tagData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <RTooltip formatter={(v: number, n: string) => [`${v} 例`, n]} />
                <Legend layout="vertical" align="right" verticalAlign="middle" iconType="circle" />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>
    </div>
  );
}
