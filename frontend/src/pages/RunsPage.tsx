import { useMemo, useState } from "react";
import {
  Button,
  Space,
  Table,
  Tabs,
} from "antd";
import { ReloadOutlined, RocketOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { RunSummary } from "../api/index";
import { RunsListOverview } from "../components/RunsListOverview";
import { CaseFilterBuilder } from "../components/CaseFilterBuilder";
import { useRunsList } from "../hooks/useRunsList";
import { useRunsTableColumns } from "../hooks/useRunsTableColumns";
import { useLatestAttributionCategoryStats } from "../hooks/useLatestAttributionCategoryStats";
import {
  filterRunsByPeriod,
  previousPeriodBounds,
  type RunsDateRangeValue,
  toPeriodBounds,
} from "../utils/runsDateRange";
import {
  computeRunsPeriodDeltas,
  filterRuns,
  type RunsListFilter,
} from "../utils/runsListOverview";
import {
  buildRunFilterValueOptions,
  filterRunRows,
  RUN_FILTER_FIELDS,
  type RunFilterCondition,
} from "../utils/runFilters";

type RunTriggerTab = "all" | "manual" | "open_api" | "scheduled";

const RUN_TRIGGER_TABS: Array<{ key: RunTriggerTab; label: string }> = [
  { key: "all", label: "全部" },
  { key: "manual", label: "人工触发" },
  { key: "open_api", label: "Open API 触发" },
  { key: "scheduled", label: "定时任务触发" },
];

function filterRunsByTrigger(runs: RunSummary[], tab: RunTriggerTab): RunSummary[] {
  return tab === "all" ? runs : runs.filter((run) => run.trigger_type === tab);
}

export default function RunsPage() {
  const navigate = useNavigate();
  const { runs, loading, progress, reload, onDelete } = useRunsList();
  const [triggerTab, setTriggerTab] = useState<RunTriggerTab>("all");
  const [filter, setFilter] = useState<RunsListFilter>("all");
  const [dateRange, setDateRange] = useState<RunsDateRangeValue | null>(null);
  const [conditionsByTab, setConditionsByTab] = useState<Record<RunTriggerTab, RunFilterCondition[]>>({
    all: [],
    manual: [],
    open_api: [],
    scheduled: [],
  });

  const triggerFiltered = useMemo(
    () => filterRunsByTrigger(runs, triggerTab),
    [runs, triggerTab]
  );
  const conditions = conditionsByTab[triggerTab];
  const setConditions = (next: RunFilterCondition[]) => {
    setConditionsByTab((previous) => ({ ...previous, [triggerTab]: next }));
  };

  const statusFiltered = useMemo(
    () => filterRuns(triggerFiltered, filter),
    [triggerFiltered, filter]
  );
  const conditionFiltered = useMemo(
    () => filterRunRows(statusFiltered, conditions),
    [statusFiltered, conditions]
  );
  const filterValueOptions = useMemo(
    () => buildRunFilterValueOptions(triggerFiltered),
    [triggerFiltered]
  );
  const triggerTabCounts = useMemo(
    () => Object.fromEntries(RUN_TRIGGER_TABS.map((tab) => [tab.key, filterRunsByTrigger(runs, tab.key).length])) as Record<RunTriggerTab, number>,
    [runs]
  );
  const { stats: attributionCategoryStats, loading: attributionCategoryStatsLoading } =
    useLatestAttributionCategoryStats(runs);

  const { displayRuns, periodBounds, previousBounds, periodDeltas } = useMemo(() => {
    if (!dateRange) {
      return {
        displayRuns: conditionFiltered,
        periodBounds: null,
        previousBounds: null,
        periodDeltas: null,
      };
    }
    const bounds = toPeriodBounds(dateRange);
    const prevBounds = previousPeriodBounds(bounds);
    const current = filterRunsByPeriod(conditionFiltered, bounds);
    const previous = filterRunsByPeriod(conditionFiltered, prevBounds);
    return {
      displayRuns: current,
      periodBounds: bounds,
      previousBounds: prevBounds,
      periodDeltas: computeRunsPeriodDeltas(current, previous),
    };
  }, [conditionFiltered, dateRange]);

  const onDateRangeChange = (range: RunsDateRangeValue | null) => {
    setDateRange(range);
  };

  const columns = useRunsTableColumns(progress, onDelete);

  return (
    <div className="runs-page">
      <div className="runs-page__head">
        <div>
          <h1 className="runs-page__title">评测列表</h1>
          <p className="runs-page__sub">乳腺癌专科 benchmark · 全量历史记录</p>
        </div>
        <Space wrap className="runs-page__actions">
          <Button className="runs-page__btn" icon={<ReloadOutlined />} onClick={() => reload()}>
            刷新
          </Button>
          <Button
            type="primary"
            className="runs-page__btn-primary"
            icon={<RocketOutlined />}
            onClick={() => navigate("/launch")}
          >
            发起评测
          </Button>
        </Space>
      </div>

      <RunsListOverview
        runs={triggerFiltered}
        filteredRuns={displayRuns}
        filter={filter}
        onFilterChange={setFilter}
        dateRange={dateRange}
        onDateRangeChange={onDateRangeChange}
        periodBounds={periodBounds}
        previousBounds={previousBounds}
        periodDeltas={periodDeltas}
        attributionCategoryStats={attributionCategoryStats}
        attributionCategoryStatsLoading={attributionCategoryStatsLoading}
      />

      <div className="runs-table-card runs-trigger-table-card">
        <Tabs
          activeKey={triggerTab}
          onChange={(key) => setTriggerTab(key as RunTriggerTab)}
          className="runs-trigger-tabs"
          items={RUN_TRIGGER_TABS.map((tab) => ({
            key: tab.key,
            label: (
              <span>
                {tab.label}
                <span className="runs-trigger-tabs__count">{triggerTabCounts[tab.key]}</span>
              </span>
            ),
            children: (
              <>
                <div className="runs-table-card__head">
                  <h3>评测记录</h3>
                  <Space size={12}>
                    <CaseFilterBuilder
                      conditions={conditions}
                      onChange={setConditions}
                      valueOptions={filterValueOptions}
                      fields={RUN_FILTER_FIELDS}
                      defaultField="name"
                    />
                    <span className="runs-table-card__count">共 {displayRuns.length} 条</span>
                  </Space>
                </div>
                <Table
                  rowKey="id"
                  loading={loading}
                  columns={columns}
                  dataSource={displayRuns}
                  pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
                  className="runs-table"
                  tableLayout="fixed"
                  scroll={{ x: 1750 }}
                />
              </>
            ),
          }))}
        />
      </div>
    </div>
  );
}
