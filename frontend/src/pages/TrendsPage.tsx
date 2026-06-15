import { useEffect, useMemo, useState } from "react";
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
import { api, Benchmark, selectableBenchmarks, TrendPoint } from "../api";
import { palette } from "../theme";

export default function TrendsPage() {
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [benchmarkId, setBenchmarkId] = useState<number | undefined>();
  const [points, setPoints] = useState<TrendPoint[]>([]);

  useEffect(() => {
    api.listBenchmarks().then((all) => {
      const bs = selectableBenchmarks(all);
      setBenchmarks(bs);
      if (bs.length) setBenchmarkId(bs[0].id);
    });
  }, []);

  useEffect(() => {
    if (benchmarkId != null) api.getTrends(benchmarkId).then((d) => setPoints(d.points));
  }, [benchmarkId]);

  const data = useMemo(
    () =>
      points.map((p) => {
        const ci = p.pass_rate_ci || {};
        const rate = p.pass_rate * 100;
        // ErrorBar 取通过率点估计到上下界的非对称半宽（百分比），无 CI 时为 0。
        const ciErr =
          ci.low != null && ci.high != null
            ? [Number((rate - ci.low * 100).toFixed(1)), Number((ci.high * 100 - rate).toFixed(1))]
            : undefined;
        return {
          name: p.name || p.run_slug,
          通过率: Number(rate.toFixed(1)),
          通过率CI: ciErr,
          综合分: p.avg_composite != null ? Number((p.avg_composite * 100).toFixed(1)) : null,
        };
      }),
    [points]
  );

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
      {data.length === 0 ? (
        <Empty description="该 benchmark 暂无成功的评测记录" />
      ) : (
        <Space direction="vertical" style={{ width: "100%" }} size={24}>
          <ResponsiveContainer width="100%" height={360}>
            <LineChart data={data}>
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
