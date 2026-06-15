import { Card, Empty, Select, Space } from "antd";
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
import { useTrendsPage } from "../hooks/useTrendsPage";

export default function TrendsPage() {
  const { benchmarks, benchmarkId, setBenchmarkId, chartData } = useTrendsPage();

  return (
    <Card
      title="跨 run 趋势看板"
      extra={
        <Select
          style={{ width: 320 }}
          value={benchmarkId}
          onChange={setBenchmarkId}
          options={benchmarks.map((b) => ({ value: b.id, label: b.name }))}
        />
      }
    >
      {chartData.length === 0 ? (
        <Empty description="该 benchmark 暂无成功的评测记录" />
      ) : (
        <Space direction="vertical" style={{ width: "100%" }} size={24}>
          <ResponsiveContainer width="100%" height={360}>
            <LineChart data={chartData}>
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: palette.muted, fontSize: 12 }} />
              <YAxis domain={[0, 100]} unit="%" axisLine={false} tickLine={false} tick={{ fill: palette.muted, fontSize: 12 }} />
              <RTooltip />
              <Legend iconType="circle" />
              <Line type="monotone" dataKey="通过率" stroke={palette.chart.teal} strokeWidth={1.5} dot={{ r: 2.5 }}>
                <ErrorBar dataKey="通过率CI" width={4} strokeWidth={1} stroke={palette.chart.muted} direction="y" />
              </Line>
              <Line type="monotone" dataKey="综合分" stroke={palette.chart.ink} strokeWidth={1.5} dot={{ r: 2.5 }} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </Space>
      )}
    </Card>
  );
}
