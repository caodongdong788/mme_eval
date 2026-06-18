import { useMemo, useState, type ReactNode } from "react";
import { Alert, Empty, Segmented, Select, Space, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Link } from "react-router-dom";
import { DiffCaseRow, RunDiff, RunSummary } from "../api/index";

type DiffFilter = "changed" | "regression" | "improvement" | "all";

function Dot({ kind, children }: { kind: string; children: ReactNode }) {
  return <span className={`status-dot status-dot--${kind}`}>{children}</span>;
}

function buildDiffColumns(runId: number): ColumnsType<DiffCaseRow> {
  return [
    {
      title: "场景描述",
      dataIndex: "sub_scenario",
      render: (s: string, r: DiffCaseRow) => (
        <Link
          to={`/runs/${runId}/cases/${r.sample_id}`}
          state={{ from: { to: `/runs/${runId}`, state: { tab: "diff" }, label: "版本对比" } }}
          className="dash-table__link"
        >
          {s || r.sample_id}
        </Link>
      ),
    },
    { title: "类别", dataIndex: "scenario" },
    { title: "Level", dataIndex: "level" },
    {
      title: "变化",
      dataIndex: "change",
      render: (c: DiffCaseRow["change"]) =>
        c === "regression" ? (
          <Dot kind="fail">劣化</Dot>
        ) : c === "improvement" ? (
          <Dot kind="pass">改善</Dot>
        ) : (
          <Typography.Text type="secondary">持平</Typography.Text>
        ),
    },
    {
      title: "当前上线",
      dataIndex: "current_release_passed",
      render: (v: boolean | null) =>
        v == null ? (
          <Typography.Text type="secondary">—</Typography.Text>
        ) : v ? (
          <Dot kind="pass">通过</Dot>
        ) : (
          <Dot kind="fail">失败</Dot>
        ),
    },
    {
      title: "基线上线",
      dataIndex: "baseline_release_passed",
      render: (v: boolean | null) =>
        v == null ? (
          <Typography.Text type="secondary">—</Typography.Text>
        ) : v ? (
          <Dot kind="pass">通过</Dot>
        ) : (
          <Dot kind="fail">失败</Dot>
        ),
    },
    {
      title: "当前综合分",
      dataIndex: "current_score",
      render: (v: number | null) =>
        v == null ? (
          <Typography.Text type="secondary">—</Typography.Text>
        ) : (
          <span className="mono">{v.toFixed(2)}</span>
        ),
    },
    {
      title: "基线综合分",
      dataIndex: "baseline_score",
      render: (v: number | null) =>
        v == null ? (
          <Typography.Text type="secondary">—</Typography.Text>
        ) : (
          <span className="mono">{v.toFixed(2)}</span>
        ),
    },
    {
      title: "分差",
      dataIndex: "score_delta",
      render: (v: number | null) => {
        if (v == null) return <Typography.Text type="secondary">—</Typography.Text>;
        const kind = v > 0 ? "pass" : v < 0 ? "fail" : "secondary";
        if (kind === "secondary") return <span className="mono">0.00</span>;
        return (
          <span className={`mono status-dot status-dot--${kind}`}>
            {v > 0 ? "+" : ""}
            {v.toFixed(2)}
          </span>
        );
      },
    },
  ];
}

export interface RunDiffTabProps {
  runId: number;
  otherRuns: RunSummary[];
  diff: RunDiff | null;
  diffBaselineId: number | null;
  diffLoading: boolean;
  onSelectBaseline: (runId: number) => void;
}

export function RunDiffTab({
  runId,
  otherRuns,
  diff,
  diffBaselineId,
  diffLoading,
  onSelectBaseline,
}: RunDiffTabProps) {
  const [filter, setFilter] = useState<DiffFilter>("changed");

  const allRows = useMemo(() => diff?.cases ?? [], [diff?.cases]);

  const shownRows = useMemo(() => {
    if (filter === "all") return allRows;
    if (filter === "regression") return allRows.filter((r) => r.change === "regression");
    if (filter === "improvement") return allRows.filter((r) => r.change === "improvement");
    return allRows.filter((r) => r.change !== "unchanged");
  }, [allRows, filter]);

  const columns = useMemo(() => buildDiffColumns(runId), [runId]);

  if (otherRuns.length === 0) {
    return (
      <div className="run-detail-page">
        <div className="dash-table-card">
          <div className="dash-table-card__head">
            <h3>版本对比</h3>
          </div>
          <div className="run-detail-page__body">
            <Empty description="暂无其它成功的评测可作对比" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="run-detail-page">
      <div className="dash-table-card">
        <div className="dash-table-card__head">
          <h3>版本对比</h3>
          {diff && (
            <span className="dash-table-card__count">
              劣化 {diff.regressions.length} · 改善 {diff.improvements.length}
            </span>
          )}
        </div>

        <div className="run-detail-page__toolbar">
          <Select
            placeholder="选择一个历史 run 作为对比基线"
            style={{ width: 360 }}
            value={diffBaselineId ?? undefined}
            options={otherRuns.map((r) => ({
              value: r.id,
              label: `#${r.id} ${r.name || r.run_slug}`,
            }))}
            onChange={(v) => onSelectBaseline(v)}
            loading={diffLoading}
          />
        </div>

        {!diff && !diffLoading && (
          <div className="run-detail-page__body">
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="请选择基线 run 查看对比明细" />
          </div>
        )}

        {diff && (
          <div className="run-detail-page__body">
            <Space direction="vertical" size={14} style={{ display: "flex", width: "100%" }}>
              <Alert
                type={diff.pass_rate_delta >= 0 ? "success" : "warning"}
                showIcon
                message={`通过率变化 ${(diff.pass_rate_delta * 100).toFixed(1)}%（当前 ${(diff.current.pass_rate * 100).toFixed(1)}% vs 基线 ${(diff.against.pass_rate * 100).toFixed(1)}%）`}
                description={
                  <>
                    劣化 {diff.regressions.length} 例 · 改善 {diff.improvements.length} 例 · 判分逻辑
                    {diff.judge_logic_changed ? "已变更（对比结果可能含尺子变化）" : "未变"}
                  </>
                }
              />

              {diff.judge_logic_changed && (
                <Alert
                  type="info"
                  showIcon
                  message="两次评测的判分逻辑或算分口径不一致，上线通过/失败的对比仅供参考。"
                />
              )}

              <Segmented<DiffFilter>
                value={filter}
                onChange={(v) => setFilter(v)}
                options={[
                  {
                    label: `有变化 (${allRows.filter((r) => r.change !== "unchanged").length})`,
                    value: "changed",
                  },
                  { label: `劣化 (${diff.regressions.length})`, value: "regression" },
                  { label: `改善 (${diff.improvements.length})`, value: "improvement" },
                  { label: `全部 (${allRows.length})`, value: "all" },
                ]}
              />

              <Table<DiffCaseRow>
                className="dash-table"
                rowKey="sample_id"
                size="small"
                loading={diffLoading}
                columns={columns}
                dataSource={shownRows}
                pagination={{ pageSize: 50, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
                locale={{ emptyText: "当前筛选下无对应用例" }}
              />
            </Space>
          </div>
        )}
      </div>
    </div>
  );
}
