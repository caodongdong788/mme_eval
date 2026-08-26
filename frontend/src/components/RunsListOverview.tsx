import { useEffect, useMemo, useState } from "react";
import { CalendarOutlined } from "@ant-design/icons";
import { DatePicker } from "antd";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import type { RunsOverviewMetrics, RunSummary } from "../api/types";
import { DeferredRunAttributionCategoryCharts } from "./DeferredRunAttributionCategoryCharts";
import { palette, trendSeriesColors } from "../theme";
import {
  formatPeriodLabel,
  getRunsDatePresetRange,
  isSameDateRange,
  RUNS_DATE_PRESETS,
  RUNS_DATE_QUICK_PRESETS,
  type RunsDateRangeValue,
  type RunsPeriodBounds,
} from "../utils/runsDateRange";
import {
  buildPassRateTrend,
  buildCxAgentOptimizationTrend,
  computeRunsListKpis,
  countRunsByFilter,
  type RunsListFilter,
  type CxAgentOptimizationPeriodDeltas,
  type RunsPeriodDeltas,
} from "../utils/runsListOverview";
import { PeriodDeltaBadge, PERIOD_COMPARE_TIP, RunsKpi } from "./RunsKpi";

const D = palette.dashboard;

const FILTER_TABS: { key: RunsListFilter; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "success", label: "已完成" },
  { key: "running", label: "进行中" },
  { key: "failed", label: "失败" },
  { key: "pinned", label: "已置顶" },
];

const FILTER_HINT: Record<RunsListFilter, string> = {
  all: "全部评测记录",
  success: "仅已完成（success）",
  running: "仅进行中（running / pending）",
  failed: "仅失败（failed）",
  pinned: "仅置顶保护的评测",
};

export function RunsListOverview({
  runs,
  filteredRuns,
  filter,
  onFilterChange,
  dateRange,
  onDateRangeChange,
  periodBounds,
  previousBounds,
  periodDeltas,
  cxAgentOptimizationPeriodDeltas,
}: {
  runs: RunSummary[];
  filteredRuns: RunSummary[];
  filter: RunsListFilter;
  onFilterChange: (f: RunsListFilter) => void;
  dateRange: RunsDateRangeValue | null;
  onDateRangeChange: (range: RunsDateRangeValue | null) => void;
  periodBounds: RunsPeriodBounds | null;
  previousBounds: RunsPeriodBounds | null;
  periodDeltas: RunsPeriodDeltas | null;
  cxAgentOptimizationPeriodDeltas: CxAgentOptimizationPeriodDeltas | null;
}) {
  const filterCounts = countRunsByFilter(runs);
  const kpis = computeRunsListKpis(filteredRuns);
  const passRateTrend = buildPassRateTrend(filteredRuns);
  const trend = passRateTrend.points;
  const cxAgentOptimizationTrend = buildCxAgentOptimizationTrend(filteredRuns);
  const completedRunIdsKey = useMemo(
    () =>
      filteredRuns
        .filter((run) => run.status === "success")
        .map((run) => run.id)
        .sort((a, b) => a - b)
        .join(","),
    [filteredRuns]
  );
  const [overviewMetrics, setOverviewMetrics] = useState<RunsOverviewMetrics | null>(null);
  const [overviewMetricsLoading, setOverviewMetricsLoading] = useState(false);

  useEffect(() => {
    const runIds = completedRunIdsKey
      ? completedRunIdsKey.split(",").map((value) => Number(value))
      : [];
    let active = true;
    if (runIds.length === 0) {
      setOverviewMetrics(null);
      setOverviewMetricsLoading(false);
      return () => {
        active = false;
      };
    }
    setOverviewMetricsLoading(true);
    api
      .getRunsOverviewMetrics(runIds)
      .then((data) => {
        if (active) setOverviewMetrics(data);
      })
      .catch(() => {
        if (active) setOverviewMetrics(null);
      })
      .finally(() => {
        if (active) setOverviewMetricsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [completedRunIdsKey]);

  const dimensionAverages = overviewMetrics?.dimension_averages.filter((item) => item.average != null) ?? [];
  // 类别过多时保留风险最高的前三项，图表用于快速定位优先处理的类别。
  // 服务端已按失败率、失败数量和样本量降序排序。
  const categoryFailureRates = (overviewMetrics?.case_type_failure_rates ?? []).slice(0, 3);
  const categoryChartHeight = Math.max(220, categoryFailureRates.length * 34 + 16);
  const passRateDelta = periodDeltas?.passRatePct ?? null;
  const cxAgentOptimizationDelta = cxAgentOptimizationPeriodDeltas?.total ?? null;
  const cxAgentOptimizationP0Delta = cxAgentOptimizationPeriodDeltas?.p0Total ?? null;
  const latestPass = trend.length ? trend[trend.length - 1].passPct : null;
  const hasPeriod = periodBounds != null && previousBounds != null;

  return (
    <div className="runs-overview">
      <div className="runs-toolbar">
        <div className="runs-tabs" role="tablist" aria-label="评测列表筛选">
          {FILTER_TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={filter === t.key}
              className={`runs-tab${filter === t.key ? " is-active" : ""}`}
              onClick={() => onFilterChange(t.key)}
            >
              {t.label}
              <span className="runs-tab__count">{filterCounts[t.key]}</span>
            </button>
          ))}
        </div>
        <div className="runs-date-filter">
          <div className="runs-date-quick" role="group" aria-label="日期快捷筛选">
            {RUNS_DATE_QUICK_PRESETS.map((p) => {
              const presetRange = getRunsDatePresetRange(p.key);
              const active = isSameDateRange(dateRange, presetRange);
              return (
                <button
                  key={p.key}
                  type="button"
                  className={`runs-date-quick__btn${active ? " is-active" : ""}`}
                  onClick={() => onDateRangeChange(presetRange)}
                >
                  {p.label}
                </button>
              );
            })}
          </div>
          <CalendarOutlined className="runs-date-filter__icon" aria-hidden />
          <DatePicker.RangePicker
            className="runs-date-filter__picker"
            value={dateRange}
            onChange={(vals) => {
              if (!vals || !vals[0] || !vals[1]) {
                onDateRangeChange(null);
                return;
              }
              onDateRangeChange([vals[0], vals[1]]);
            }}
            allowClear
            presets={RUNS_DATE_PRESETS}
            placeholder={["开始日期", "结束日期"]}
          />
        </div>
      </div>

      {hasPeriod && (
        <p className="runs-filter-hint">
          统计周期 {formatPeriodLabel(periodBounds)} · 上周期 {formatPeriodLabel(previousBounds)}
          {filter !== "all" ? ` · ${FILTER_HINT[filter]}` : ""}
        </p>
      )}
      {!hasPeriod && filter !== "all" && (
        <p className="runs-filter-hint">
          当前筛选：{FILTER_HINT[filter]} · 共 {filteredRuns.length} 条 · 选择日期范围后可看上周期环比
        </p>
      )}

      <div className="runs-kpi-row">
        <RunsKpi
          title="评测总数"
          tip={
            hasPeriod
              ? `统计周期内评测次数 · ${PERIOD_COMPARE_TIP}`
              : filter === "all"
                ? "含成功、失败、进行中；选择日期后可看上周期环比"
                : FILTER_HINT[filter]
          }
          value={String(kpis.total)}
          unit="次"
          trend={
            hasPeriod && periodDeltas ? (
              <PeriodDeltaBadge delta={periodDeltas.total} unit="次" />
            ) : undefined
          }
        />
        <RunsKpi
          title="平均通过率"
          tip={`每天取当天实际完成的各 Benchmark 最新一次评测，按通过 Case 数 ÷ Case 总数聚合；不同日期的 Benchmark 覆盖范围可能不同${hasPeriod ? ` · ${PERIOD_COMPARE_TIP}` : ""}`}
          value={kpis.avgPassPct != null ? kpis.avgPassPct.toFixed(1) : "—"}
          unit={kpis.avgPassPct != null ? "%" : undefined}
          trend={hasPeriod ? <PeriodDeltaBadge delta={passRateDelta} percent /> : undefined}
        />
        <RunsKpi
          title="医学安全性失败"
          tip={`当前范围内已完成评测的医学安全性失败用例累计${hasPeriod ? ` · ${PERIOD_COMPARE_TIP}` : ""}`}
          value={String(kpis.medicalSafetyFailedTotal)}
          unit="例"
          trend={
            hasPeriod && periodDeltas ? (
              <PeriodDeltaBadge delta={periodDeltas.medicalSafetyFailed} unit="例" invertColor />
            ) : undefined
          }
        />
        <RunsKpi
          title="平均分"
          tip={`仅统计当前筛选中已完成评测的总分均值（每个评测任务等权；不同评分标准的满分可能不同）${hasPeriod ? ` · ${PERIOD_COMPARE_TIP}` : ""}`}
          value={kpis.avgComposite != null ? kpis.avgComposite.toFixed(1) : "—"}
          unit={kpis.avgComposite != null ? "分" : undefined}
          trend={
            hasPeriod && periodDeltas ? (
              <PeriodDeltaBadge delta={periodDeltas.avgComposite} unit="分" />
            ) : undefined
          }
        />
      </div>

      <div className="runs-chart-card runs-chart-card--main runs-overview__pass-trend">
        <div className="runs-chart-card__head">
          <div className="runs-chart-card__title">通过率趋势</div>
        </div>
        {trend.length > 0 && (
          <div className="runs-mini-kpis">
            <div>
              <div className="runs-mini-kpi__label">最新通过率</div>
              <div className="runs-mini-kpi__val">{latestPass}%</div>
            </div>
            <div>
              <div className="runs-mini-kpi__label">平均通过率</div>
              <div className="runs-mini-kpi__val">
                {kpis.avgPassPct != null ? `${kpis.avgPassPct.toFixed(1)}%` : "—"}
              </div>
            </div>
            <div>
              <div className="runs-mini-kpi__label">较上周期</div>
              <div
                className="runs-mini-kpi__val"
                style={{
                  color:
                    passRateDelta == null
                      ? D.textMuted
                      : passRateDelta >= 0
                        ? D.teal
                        : D.red,
                }}
              >
                {passRateDelta != null
                  ? `${passRateDelta >= 0 ? "+" : ""}${passRateDelta}%`
                  : "—"}
              </div>
            </div>
          </div>
        )}
        <div className="runs-chart-area">
          {trend.length === 0 ? (
            <div className="runs-chart-empty">
              {filter === "success" || filter === "all"
                ? "当前范围内暂无已完成评测，无法绘制趋势"
                : "当前筛选暂无已完成评测，无法绘制趋势"}
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <ComposedChart data={trend} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
                <defs>
                  <linearGradient id="runsPassFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={D.purpleLine} stopOpacity={0.22} />
                    <stop offset="100%" stopColor={D.purpleLine} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={D.border} vertical={false} />
                <XAxis
                  dataKey="timestamp"
                  type="number"
                  scale="time"
                  domain={passRateTrend.xDomain || ["dataMin", "dataMax"]}
                  ticks={passRateTrend.dateTicks}
                  tickFormatter={(timestamp) => {
                    const date = new Date(Number(timestamp));
                    return `${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
                  }}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: D.textMuted, fontSize: 11 }}
                />
                <YAxis
                  domain={[0, 100]}
                  unit="%"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: D.textMuted, fontSize: 11 }}
                />
                <RTooltip
                  labelFormatter={(timestamp) => {
                    const date = new Date(Number(timestamp));
                    return `${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
                  }}
                  formatter={(value, _name, item) => {
                    const point = item.payload as { passed: number; total: number; benchmarkCount: number };
                    return [
                      `${Number(value)}%（${point.passed}/${point.total}，覆盖 ${point.benchmarkCount} 个 Benchmark）`,
                      "聚合通过率",
                    ];
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="passPct"
                  stroke={D.purpleLine}
                  fill="url(#runsPassFill)"
                  strokeWidth={2}
                  dot={{ r: 3, fill: D.card, stroke: D.purpleLine, strokeWidth: 2 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="runs-chart-card runs-chart-card--main runs-overview__cx-agent-trend">
        <div className="runs-chart-card__head">
          <div className="runs-chart-card__title">cx-agent 归因优化点趋势</div>
        </div>
        {cxAgentOptimizationTrend.series.length > 0 && (
          <div className="runs-mini-kpis">
            <div>
              <div className="runs-mini-kpi__label">最新优化点</div>
              <div className="runs-mini-kpi__val">
                {cxAgentOptimizationTrend.latestTotal == null
                  ? "—"
                  : `${cxAgentOptimizationTrend.latestTotal} 个`}
              </div>
            </div>
            <div>
              <div className="runs-mini-kpi__label">P0 优化点</div>
              <div className="runs-mini-kpi__val">
                {cxAgentOptimizationTrend.latestP0Total == null
                  ? "—"
                  : `${cxAgentOptimizationTrend.latestP0Total} 个`}
              </div>
            </div>
            <div>
              <div className="runs-mini-kpi__label">P0 较上周期</div>
              <div className="runs-mini-kpi__val" style={{ color: D.purpleLine }}>
                {cxAgentOptimizationP0Delta != null
                  ? `${cxAgentOptimizationP0Delta >= 0 ? "+" : ""}${cxAgentOptimizationP0Delta} 个`
                  : "—"}
              </div>
            </div>
            <div>
              <div className="runs-mini-kpi__label">较上周期</div>
              <div className="runs-mini-kpi__val" style={{ color: D.purpleLine }}>
                {cxAgentOptimizationDelta != null
                  ? `${cxAgentOptimizationDelta >= 0 ? "+" : ""}${cxAgentOptimizationDelta} 个`
                  : "—"}
              </div>
            </div>
          </div>
        )}
        <div className="runs-chart-area">
          {cxAgentOptimizationTrend.series.length === 0 ? (
            <div className="runs-chart-empty">当前范围内暂无已完成归因结果，完成归因后将自动展示趋势</div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <ComposedChart
                data={cxAgentOptimizationTrend.points}
                margin={{ top: 8, right: 12, bottom: 0, left: -8 }}
              >
                <CartesianGrid stroke={D.border} vertical={false} />
                <XAxis
                  dataKey="timestamp"
                  type="number"
                  scale="time"
                  domain={cxAgentOptimizationTrend.xDomain || ["dataMin", "dataMax"]}
                  ticks={cxAgentOptimizationTrend.dateTicks}
                  tickFormatter={(timestamp) => {
                    const date = new Date(Number(timestamp));
                    return `${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
                  }}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: D.textMuted, fontSize: 11 }}
                />
                <YAxis
                  allowDecimals={false}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: D.textMuted, fontSize: 11 }}
                />
                <RTooltip
                  formatter={(value, _name, item) => {
                    const seriesKey = String(item.dataKey);
                    const point = item.payload as {
                      [key: string]: string | number | undefined;
                    };
                    return [
                      `${Number(value)} 个（P0 ${Number(point[`${seriesKey}__p0`] || 0)} 个）`,
                      `${String(_name)} · ${String(point[`${seriesKey}__run_name`] || "")}`,
                    ];
                  }}
                  labelFormatter={(_label, payload) => {
                    const point = payload[0]?.payload as { name?: string } | undefined;
                    return point?.name ? `评测日期：${point.name}` : "";
                  }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                {cxAgentOptimizationTrend.series.map((series, index) => {
                  const color = trendSeriesColors[index % trendSeriesColors.length];
                  return (
                    <Line
                      key={series.key}
                      type="monotone"
                      dataKey={series.key}
                      name={series.name}
                      stroke={color}
                      strokeWidth={2}
                      connectNulls
                      dot={{ r: 3, fill: D.card, stroke: color, strokeWidth: 2 }}
                      activeDot={{ r: 5 }}
                    />
                  );
                })}
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="runs-overview__attribution-categories">
        <DeferredRunAttributionCategoryCharts runs={runs} />
      </div>

      <div className="runs-duo-charts runs-overview__metrics">
        <div className="runs-chart-card">
          <div className="runs-chart-card__title">八维度平均分</div>
          <div className="runs-chart-card__subtitle">仅统计当前筛选中已完成的 Agent 评测八维结果</div>
          <div className="runs-chart-area runs-chart-area--metrics">
            {overviewMetricsLoading ? (
              <div className="runs-chart-empty">正在汇总当前筛选的评测结果</div>
            ) : dimensionAverages.length === 0 ? (
              <div className="runs-chart-empty">当前筛选中暂无可展示的八维评分结果</div>
            ) : (
              <ResponsiveContainer width="100%" height={272}>
                <BarChart
                  layout="vertical"
                  data={dimensionAverages}
                  margin={{ top: 6, right: 24, bottom: 0, left: 4 }}
                >
                  <CartesianGrid stroke={D.border} horizontal={false} />
                  <XAxis
                    type="number"
                    domain={[0, 5]}
                    ticks={[0, 1, 2, 3, 4, 5]}
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: D.textMuted, fontSize: 11 }}
                  />
                  <YAxis
                    type="category"
                    dataKey="label"
                    width={132}
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: D.textMuted, fontSize: 11 }}
                  />
                  <RTooltip
                    formatter={(value, _name, item) => [
                      `${Number(value).toFixed(2)} / 5`,
                      `${String(item.payload?.label ?? "")}平均分`,
                    ]}
                  />
                  <Bar dataKey="average" name="平均分" radius={[0, 4, 4, 0]} maxBarSize={20}>
                    {dimensionAverages.map((_, i) => (
                      <Cell key={i} fill={i % 2 ? D.purpleLine : D.purple} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
        <div className="runs-chart-card">
          <div className="runs-chart-card__title">类别失败率</div>
          <div className="runs-chart-card__subtitle">按最终结论失败率从高到低排序</div>
          <div className="runs-chart-area runs-chart-area--metrics">
            {overviewMetricsLoading ? (
              <div className="runs-chart-empty">正在汇总当前筛选的类别结果</div>
            ) : categoryFailureRates.length === 0 ? (
              <div className="runs-chart-empty">当前筛选中暂无类别统计结果</div>
            ) : (
              <div className="runs-metric-chart-scroll">
                <div className="runs-metric-chart-canvas" style={{ height: categoryChartHeight }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      layout="vertical"
                      data={categoryFailureRates}
                      margin={{ top: 6, right: 32, bottom: 0, left: 6 }}
                    >
                      <CartesianGrid stroke={D.border} horizontal={false} />
                      <XAxis
                        type="number"
                        domain={[0, 100]}
                        unit="%"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: D.textMuted, fontSize: 11 }}
                      />
                      <YAxis
                        type="category"
                        dataKey="case_type"
                        width={148}
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: D.textMuted, fontSize: 11 }}
                      />
                      <RTooltip
                        labelFormatter={(label) => `类别：${String(label)}`}
                        formatter={(value, _name, item) => {
                          const row = item.payload as (typeof categoryFailureRates)[number];
                          return [`${Number(value).toFixed(1)}%（${row.failed}/${row.total}）`, "失败率"];
                        }}
                      />
                      <Bar dataKey="failure_rate" name="失败率" fill={D.red} radius={[0, 4, 4, 0]} maxBarSize={20}>
                        {categoryFailureRates.map((_, i) => (
                          <Cell key={i} fill={i === 0 ? D.red : D.redMuted} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
