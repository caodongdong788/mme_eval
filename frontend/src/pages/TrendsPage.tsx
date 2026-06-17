import { Empty, Select } from "antd";
import {
  ErrorBar,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { palette } from "../theme";
import { AsyncLoadError } from "../components/AsyncLoadError";
import { DashboardPageShell } from "../components/DashboardPageShell";
import { useTrendsPage } from "../hooks/useTrendsPage";

export default function TrendsPage() {
  const { benchmarks, benchmarkId, setBenchmarkId, chartData, loadError, reload } = useTrendsPage();

  return (
    <DashboardPageShell
      title="跨 run 趋势看板"
      sub="同一 benchmark 下多次评测的通过率与综合分走势"
      extra={
        <Select
          style={{ width: 320 }}
          value={benchmarkId}
          onChange={setBenchmarkId}
          options={benchmarks.map((b) => ({ value: b.id, label: b.name }))}
        />
      }
    >
      <div className="runs-chart-card runs-chart-card--main">
        {loadError ? (
          <AsyncLoadError message={loadError} onRetry={reload} />
        ) : chartData.length === 0 ? (
          <Empty description="该 benchmark 暂无成功的评测记录" />
        ) : (
          <ResponsiveContainer width="100%" height={360}>
            <LineChart data={chartData}>
              <XAxis
                dataKey="name"
                axisLine={false}
                tickLine={false}
                tick={{ fill: palette.dashboard.textMuted, fontSize: 12 }}
              />
              <YAxis
                domain={[0, 100]}
                unit="%"
                axisLine={false}
                tickLine={false}
                tick={{ fill: palette.dashboard.textMuted, fontSize: 12 }}
              />
              <RTooltip />
              <Legend iconType="circle" />
              <Line
                type="monotone"
                dataKey="通过率"
                stroke={palette.dashboard.purple}
                strokeWidth={1.5}
                dot={{ r: 2.5 }}
              >
                <ErrorBar
                  dataKey="通过率CI"
                  width={4}
                  strokeWidth={1}
                  stroke={palette.dashboard.textMuted}
                  direction="y"
                />
              </Line>
              <Line
                type="monotone"
                dataKey="综合分"
                stroke={palette.dashboard.teal}
                strokeWidth={1.5}
                dot={{ r: 2.5 }}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </DashboardPageShell>
  );
}
