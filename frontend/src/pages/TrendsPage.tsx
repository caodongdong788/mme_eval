import { Empty, Select, Tabs } from "antd";
import { useEffect, useMemo, useState } from "react";
import {
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, ScheduledEvaluation, TrendPoint } from "../api/index";
import { AsyncLoadError } from "../components/AsyncLoadError";
import { DashboardPageShell } from "../components/DashboardPageShell";
import { RunsChartCard } from "../components/RunsChartCard";
import { useAsyncData } from "../hooks/useAsyncData";
import { useTrendsPage } from "../hooks/useTrendsPage";
import { DIM_LABEL, EVALUATION_DIMENSIONS } from "../labels";
import { palette } from "../theme";

type ChartRow = Record<string, string | number | null>;
type TrendSeries = { key: string; label: string; color: string };

const SERIES_COLORS = [
  palette.dashboard.purple,
  palette.dashboard.teal,
  "#3f8cff",
  "#e38b17",
  "#d25b9b",
  "#6fba55",
  "#8b6bd6",
  "#13a6a1",
];

function asNumber(value: unknown): number | null {
  if (value == null || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function pct(value: unknown): number | null {
  const number = asNumber(value);
  return number == null ? null : Number((number * 100).toFixed(1));
}

function chartRows(points: TrendPoint[]): ChartRow[] {
  return points.map((point) => ({
    label: `#${point.run_id}`,
    运行: point.name || point.run_slug,
    完成时间: point.finished_at ? new Date(point.finished_at).toLocaleString("zh-CN", { hour12: false }) : "—",
    通过率: pct(point.pass_rate),
    "综合分（/45）": asNumber(point.avg_composite),
    "安全失败数": point.medical_safety_failed,
    "平均耗时（ms）": asNumber(point.latency_summary?.avg_ms),
    "P90 耗时（ms）": asNumber(point.latency_summary?.p90_ms),
    "平均 TTFT（ms）": asNumber(point.ttft_summary?.avg_ms),
    "总 Token": asNumber(point.token_summary?.total_tokens ?? point.token_summary?.total),
    "平均 Token": asNumber(point.token_summary?.avg_tokens_per_run ?? point.token_summary?.avg_per_case),
    "pass@k": pct(point.reliability?.pass_at_k),
    "pass^k": pct(point.reliability?.pass_all_k),
    "波动用例": asNumber(point.reliability?.flaky_cases),
    ...Object.fromEntries(
      Object.entries(point.avg_dimension || {}).map(([key, value]) => [DIM_LABEL[key] || key, asNumber(value)])
    ),
    ...Object.fromEntries(
      Object.entries(point.by_case_type || {}).map(([name, bucket]) => [
        `类别：${name || "未分类"}`,
        bucket.total ? Number(((bucket.passed / bucket.total) * 100).toFixed(1)) : null,
      ])
    ),
  }));
}

function TrendChart({
  data,
  series,
  unit,
  domain,
}: {
  data: ChartRow[];
  series: TrendSeries[];
  unit?: string;
  domain?: [number | "auto", number | "auto"];
}) {
  if (!data.length || !series.length) return <Empty description="暂无可展示的趋势数据" />;
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 8, right: 22, bottom: 4, left: 2 }}>
        <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: palette.dashboard.textMuted, fontSize: 12 }} />
        <YAxis
          domain={domain}
          unit={unit}
          axisLine={false}
          tickLine={false}
          tick={{ fill: palette.dashboard.textMuted, fontSize: 12 }}
        />
        <RTooltip labelFormatter={(label) => `${label} · ${String(data.find((row) => row.label === label)?.运行 || "")}`} />
        <Legend iconType="circle" />
        {series.map((item) => (
          <Line
            key={item.key}
            type="monotone"
            dataKey={item.key}
            name={item.label}
            stroke={item.color}
            strokeWidth={1.8}
            dot={{ r: 2.5 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function TrendAnalysisSections({ points, loading }: { points: TrendPoint[]; loading: boolean }) {
  const data = useMemo(() => chartRows(points), [points]);
  const dimensionSeries = useMemo(
    () =>
      EVALUATION_DIMENSIONS.filter((key) => data.some((row) => row[DIM_LABEL[key]] != null)).map((key, index) => ({
        key: DIM_LABEL[key],
        label: DIM_LABEL[key],
        color: SERIES_COLORS[index % SERIES_COLORS.length],
      })),
    [data]
  );
  const caseTypeSeries = useMemo(() => {
    const names = Array.from(
      new Set(data.flatMap((row) => Object.keys(row).filter((key) => key.startsWith("类别："))))
    ).sort((a, b) => a.localeCompare(b, "zh-CN"));
    return names.map((name, index) => ({ key: name, label: name.replace("类别：", ""), color: SERIES_COLORS[index % SERIES_COLORS.length] }));
  }, [data]);

  return (
    <div className="trends-sections">
      <RunsChartCard title="每次评测结果：通过率" empty={loading || data.length === 0}>
        <TrendChart data={data} series={[{ key: "通过率", label: "通过率", color: palette.dashboard.purple }]} unit="%" domain={[0, 100]} />
      </RunsChartCard>
      <RunsChartCard title="八维平均分趋势" empty={loading || dimensionSeries.length === 0}>
        <TrendChart data={data} series={dimensionSeries} domain={[0, 5]} />
      </RunsChartCard>
      <div className="runs-duo-charts trends-duo-charts">
        <RunsChartCard title="性能趋势（平均 / P90 / 首 Token 耗时）" empty={loading || data.length === 0}>
          <TrendChart
            data={data}
            series={[
              { key: "平均耗时（ms）", label: "平均耗时", color: palette.dashboard.purple },
              { key: "P90 耗时（ms）", label: "P90 耗时", color: "#e38b17" },
              { key: "平均 TTFT（ms）", label: "平均首 Token 耗时", color: palette.dashboard.teal },
            ]}
            unit="ms"
          />
        </RunsChartCard>
        <RunsChartCard title="Token 消耗趋势" empty={loading || data.length === 0}>
          <TrendChart
            data={data}
            series={[
              { key: "总 Token", label: "总 Token", color: palette.dashboard.purple },
              { key: "平均 Token", label: "平均每次", color: palette.dashboard.teal },
            ]}
          />
        </RunsChartCard>
      </div>
      <div className="runs-duo-charts trends-duo-charts">
        <RunsChartCard title="可靠性趋势（pass@k / pass^k）" empty={loading || data.length === 0}>
          <TrendChart
            data={data}
            series={[
              { key: "pass@k", label: "pass@k", color: palette.dashboard.purple },
              { key: "pass^k", label: "pass^k（全成功）", color: palette.dashboard.teal },
            ]}
            unit="%"
            domain={[0, 100]}
          />
        </RunsChartCard>
        <RunsChartCard title="可靠性趋势：波动用例数" empty={loading || data.length === 0}>
          <TrendChart data={data} series={[{ key: "波动用例", label: "波动用例", color: "#e38b17" }]} />
        </RunsChartCard>
      </div>
      <RunsChartCard title="类别通过率趋势" empty={loading || caseTypeSeries.length === 0}>
        <TrendChart data={data} series={caseTypeSeries} unit="%" domain={[0, 100]} />
      </RunsChartCard>
    </div>
  );
}

function BenchmarkTrendPanel() {
  const { benchmarks, benchmarkId, setBenchmarkId, points, loading, loadError, reload } = useTrendsPage();
  return (
    <>
      <div className="trends-toolbar">
        <span>选择 Benchmark</span>
        <Select
          style={{ width: 320, maxWidth: "100%" }}
          value={benchmarkId}
          onChange={setBenchmarkId}
          options={benchmarks.map((benchmark) => ({ value: benchmark.id, label: benchmark.name }))}
        />
      </div>
      {loadError ? <AsyncLoadError message={loadError} onRetry={reload} /> : <TrendAnalysisSections points={points} loading={loading} />}
    </>
  );
}

function RegressionTrendPanel() {
  const {
    data: schedules,
    loading: schedulesLoading,
    error: schedulesError,
    reload: reloadSchedules,
  } = useAsyncData(() => api.listScheduledEvaluations(), []);
  const [scheduleId, setScheduleId] = useState<number>();

  useEffect(() => {
    if (schedules?.length && scheduleId == null) setScheduleId(schedules[0].id);
  }, [schedules, scheduleId]);

  const {
    data: regression,
    loading: regressionLoading,
    error: regressionError,
    reload: reloadRegression,
  } = useAsyncData(
    () => (scheduleId == null ? Promise.resolve(null) : api.getRegressionTrends(scheduleId)),
    [scheduleId]
  );

  const points = regression?.points || [];
  const error = schedulesError || regressionError;
  const reload = () => {
    reloadSchedules();
    if (scheduleId != null) reloadRegression();
  };
  const noSchedules = !schedulesLoading && (schedules?.length || 0) === 0;
  const noRuns = !regressionLoading && Boolean(scheduleId) && points.length === 0;

  return (
    <>
      <div className="trends-toolbar">
        <span>选择定时回归任务</span>
        <Select
          style={{ width: 360, maxWidth: "100%" }}
          value={scheduleId}
          loading={schedulesLoading}
          onChange={setScheduleId}
          placeholder="请选择定时任务"
          options={(schedules || []).map((task: ScheduledEvaluation) => ({ value: task.id, label: task.name }))}
        />
      </div>
      {error ? (
        <AsyncLoadError message={error} onRetry={reload} />
      ) : noSchedules ? (
        <div className="trends-empty"><Empty description="暂无定时任务，请先在参数配置中创建" /></div>
      ) : noRuns ? (
        <div className="trends-empty"><Empty description="该定时任务尚无成功的评测记录" /></div>
      ) : (
        <TrendAnalysisSections points={points} loading={regressionLoading} />
      )}
    </>
  );
}

export default function TrendsPage() {
  return (
    <DashboardPageShell title="趋势看板" sub="查看 Benchmark 整体趋势与定时回归任务的逐次质量变化">
      <Tabs
        className="trends-tabs"
        defaultActiveKey="benchmark"
        items={[
          { key: "benchmark", label: "Benchmark 趋势看板", children: <BenchmarkTrendPanel /> },
          { key: "regression", label: "回归任务看板", children: <RegressionTrendPanel /> },
        ]}
      />
    </DashboardPageShell>
  );
}
