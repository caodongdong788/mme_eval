import { useMemo, useState } from "react";
import {
  Button,
  Popconfirm,
  Progress,
  Space,
  Table,
  Tooltip,
} from "antd";
import { DeleteOutlined, ReloadOutlined, RocketOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { RunSummary } from "../api/index";
import { DashTableActions, DashTableDangerLink, DashTableNavLink } from "../components/DashTableActions";
import { formatApiDateTime } from "../utils/datetime";
import { RunStatusTag } from "../components/RunStatusTag";
import { RunsListOverview } from "../components/RunsListOverview";
import { FeishuMention } from "../components/FeishuMention";
import { RunTriggerTag } from "../components/RunTriggerTag";
import { CaseFilterBuilder } from "../components/CaseFilterBuilder";
import { useRunsList } from "../hooks/useRunsList";
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

export default function RunsPage() {
  const navigate = useNavigate();
  const { runs, loading, progress, reload, onDelete } = useRunsList();
  const [filter, setFilter] = useState<RunsListFilter>("all");
  const [dateRange, setDateRange] = useState<RunsDateRangeValue | null>(null);
  const [conditions, setConditions] = useState<RunFilterCondition[]>([]);

  const statusFiltered = useMemo(() => filterRuns(runs, filter), [runs, filter]);
  const conditionFiltered = useMemo(
    () => filterRunRows(statusFiltered, conditions),
    [statusFiltered, conditions]
  );
  const filterValueOptions = useMemo(() => buildRunFilterValueOptions(runs), [runs]);

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

  const nowrap = { onCell: () => ({ style: { whiteSpace: "nowrap" as const } }) };
  const wrapCell = {
    onCell: () => ({
      style: { whiteSpace: "normal" as const, wordBreak: "break-word" as const },
    }),
  };

  const columns = [
    { title: "ID", dataIndex: "id", width: "7%", ...nowrap, className: "runs-table__mono" },
    {
      title: "名称",
      dataIndex: "name",
      width: "18%",
      ...wrapCell,
      render: (name: string, r: RunSummary) => (
        <Space size={4} wrap>
          <DashTableNavLink to={`/runs/${r.id}`}>
            {name || r.run_slug}
          </DashTableNavLink>
          {r.pinned && <span className="runs-table__pin">置顶</span>}
        </Space>
      ),
    },
    {
      title: "任务类型",
      dataIndex: "trigger_type",
      width: "10%",
      ...nowrap,
      render: (type: RunSummary["trigger_type"]) => <RunTriggerTag type={type} />,
    },
    {
      title: "状态",
      dataIndex: "status",
      width: "11%",
      render: (s: string, r: RunSummary) => {
        if (s === "running" || s === "pending") {
          const p = progress[r.id]?.progress;
          return (
            <Space direction="vertical" size={2} style={{ minWidth: 140 }}>
              <RunStatusTag status={s} />
              {p && (
                <Tooltip title={`${p.current_label || ""} ${p.done || 0}/${p.total || 0}`}>
                  <Progress percent={p.percent || 0} size="small" strokeColor="var(--runs-purple)" />
                </Tooltip>
              )}
            </Space>
          );
        }
        if (s === "failed") {
          return (
            <Tooltip title={r.error_msg}>
              <RunStatusTag status={s} />
            </Tooltip>
          );
        }
        return <RunStatusTag status={s} />;
      },
    },
    {
      title: "通过率",
      dataIndex: "pass_rate",
      width: "11%",
      ...nowrap,
      render: (v: number, r: RunSummary) =>
        r.status === "success" ? (
          <span className="runs-table__pass">
            {(v * 100).toFixed(1)}% ({r.passed}/{r.total})
          </span>
        ) : (
          "—"
        ),
    },
    {
      title: "安全失败",
      dataIndex: "medical_safety_failed",
      width: "8%",
      ...nowrap,
      render: (v: number, r: RunSummary) =>
        r.status === "success" ? (
          v > 0 ? <span className="runs-table__danger">{v}</span> : "0"
        ) : (
          "—"
        ),
    },
    { title: "N", dataIndex: "n_runs", width: "4%", ...nowrap },
    {
      title: "创建人",
      dataIndex: "created_by",
      width: "10%",
      ...nowrap,
      render: (name?: string | null) => <FeishuMention name={name} />,
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      width: "11%",
      ...nowrap,
      render: (v?: string) => formatApiDateTime(v),
    },
    {
      title: "操作",
      width: "11%",
      ...wrapCell,
      render: (_: unknown, r: RunSummary) => {
        const busy = r.status === "running" || r.status === "pending";
        return (
          <DashTableActions>
            <DashTableNavLink to={`/runs/${r.id}`}>看板</DashTableNavLink>
            <Popconfirm
              title="确认删除该评测？"
              description="将一并删除其用例结果与产物，且不可恢复。"
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={() => void onDelete(r.id)}
              disabled={busy}
            >
              <DashTableDangerLink disabled={busy}>
                <DeleteOutlined /> 删除
              </DashTableDangerLink>
            </Popconfirm>
          </DashTableActions>
        );
      },
    },
  ];

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
        runs={runs}
        filteredRuns={displayRuns}
        filter={filter}
        onFilterChange={setFilter}
        dateRange={dateRange}
        onDateRangeChange={onDateRangeChange}
        periodBounds={periodBounds}
        previousBounds={previousBounds}
        periodDeltas={periodDeltas}
      />

      <div className="runs-table-card">
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
        />
      </div>
    </div>
  );
}
