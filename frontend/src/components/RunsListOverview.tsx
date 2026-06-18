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
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RunSummary } from "../api/types";
import { palette, dashboardPieColors } from "../theme";
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
  buildRecentPassBars,
  buildStatusDistribution,
  computeRunsListKpis,
  countRunsByFilter,
  type RunsListFilter,
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
}) {
  const filterCounts = countRunsByFilter(runs);
  const kpis = computeRunsListKpis(filteredRuns);
  const trend = buildPassRateTrend(filteredRuns);
  const bars = buildRecentPassBars(filteredRuns);
  const statusPie = buildStatusDistribution(filteredRuns);
  const passRateDelta = periodDeltas?.passRatePct ?? null;
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
          tip={`仅统计当前范围内已完成的评测${hasPeriod ? ` · ${PERIOD_COMPARE_TIP}` : ""}`}
          value={kpis.avgPassPct != null ? kpis.avgPassPct.toFixed(1) : "—"}
          unit={kpis.avgPassPct != null ? "%" : undefined}
          trend={hasPeriod ? <PeriodDeltaBadge delta={passRateDelta} percent /> : undefined}
        />
        <RunsKpi
          title="HardGate 失败"
          tip={`当前范围内已完成评测的硬门槛失败用例累计${hasPeriod ? ` · ${PERIOD_COMPARE_TIP}` : ""}`}
          value={String(kpis.hardGateTotal)}
          unit="例"
          trend={
            hasPeriod && periodDeltas ? (
              <PeriodDeltaBadge delta={periodDeltas.hardGate} unit="例" invertColor />
            ) : undefined
          }
        />
        <RunsKpi
          title="进行中"
          tip={`当前范围内 running / pending 状态${hasPeriod ? ` · ${PERIOD_COMPARE_TIP}` : ""}`}
          value={String(kpis.activeCount)}
          unit="次"
          trend={
            hasPeriod && periodDeltas ? (
              <PeriodDeltaBadge delta={periodDeltas.active} unit="次" />
            ) : undefined
          }
        />
      </div>

      <div className="runs-chart-card runs-chart-card--main">
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
                : "当前筛选无已完成评测，无法绘制趋势"}
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
                <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: D.textMuted, fontSize: 11 }} />
                <YAxis
                  domain={[0, 100]}
                  unit="%"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: D.textMuted, fontSize: 11 }}
                />
                <RTooltip formatter={(v: number) => [`${v}%`, "通过率"]} />
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

      <div className="runs-duo-charts">
        <div className="runs-chart-card">
          <div className="runs-chart-card__title runs-chart-card__title--solo">最近评测 · 通过率</div>
          <div className="runs-chart-area runs-chart-area--short">
            {bars.length === 0 ? (
              <div className="runs-chart-empty">当前范围内暂无已完成评测</div>
            ) : (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={bars} margin={{ top: 12, right: 8, bottom: 0, left: -12 }}>
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: D.textMuted, fontSize: 10 }} />
                  <YAxis domain={[0, 100]} unit="%" axisLine={false} tickLine={false} tick={{ fill: D.textMuted, fontSize: 10 }} />
                  <RTooltip formatter={(v: number) => [`${v}%`, "通过率"]} />
                  <Bar dataKey="passPct" radius={[4, 4, 0, 0]} maxBarSize={32}>
                    {bars.map((_, i) => (
                      <Cell key={i} fill={i % 2 ? D.purpleLine : D.purple} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
        <div className="runs-chart-card">
          <div className="runs-chart-card__title runs-chart-card__title--solo">评测状态分布</div>
          <div className="runs-chart-area runs-chart-area--short">
            {statusPie.length === 0 ? (
              <div className="runs-chart-empty">当前范围内暂无数据</div>
            ) : (
              <ResponsiveContainer width="100%" height={160}>
                <PieChart>
                  <Pie
                    data={statusPie}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={42}
                    outerRadius={62}
                    paddingAngle={2}
                  >
                    {statusPie.map((_, i) => (
                      <Cell key={i} fill={dashboardPieColors[i % dashboardPieColors.length]} />
                    ))}
                  </Pie>
                  <RTooltip />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
