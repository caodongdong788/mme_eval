import { useMemo } from "react";
import { Button, InputNumber, Table } from "antd";
import { ReleaseThresholdItem } from "../api/index";
import { AsyncLoadError } from "../components/AsyncLoadError";
import { DashTableLink } from "../components/DashTableActions";
import { DashboardPageShell } from "../components/DashboardPageShell";
import { useReleaseThresholdsPage } from "../hooks/useReleaseThresholdsPage";
import { PROFILE_LABEL } from "../labels";

function coverageLabel(r: ReleaseThresholdItem): string {
  const { is_fallback, score_profile, case_count } = r.coverage;
  const countSuffix = case_count > 0 ? ` · ${case_count} 题` : "";
  if (is_fallback) {
    return `default（兜底）${countSuffix}`;
  }
  const profileName = PROFILE_LABEL[score_profile] ?? score_profile;
  return `${profileName}${countSuffix}`;
}

function isCustomized(r: ReleaseThresholdItem, draft: Record<string, number>): boolean {
  return (draft[r.profile] ?? r.effective) !== r.default_threshold;
}

export default function ReleaseThresholdsPage() {
  const rt = useReleaseThresholdsPage();

  const customizedCount = useMemo(
    () => rt.rows.filter((r) => isCustomized(r, rt.draft)).length,
    [rt.rows, rt.draft]
  );

  const columns = [
    {
      title: "评分档",
      dataIndex: "label",
      width: 140,
      render: (_label: string, r: ReleaseThresholdItem) => (
        <div style={{ lineHeight: 1.45 }}>
          <div className="dash-table__profile-name">
            {PROFILE_LABEL[r.profile] ?? r.label ?? r.profile}
          </div>
          <div className="dash-table__profile-id">{r.profile}</div>
        </div>
      ),
    },
    {
      title: "覆盖范围（score_profile）",
      key: "coverage",
      render: (_: unknown, r: ReleaseThresholdItem) => (
        <span className={`dash-chip${r.coverage.is_fallback ? " dash-chip--fallback" : ""}`}>
          {coverageLabel(r)}
        </span>
      ),
    },
    {
      title: "满分上限",
      dataIndex: "max_total",
      width: 100,
      render: (v: number) => <span className="mono">{v.toFixed(2)}</span>,
    },
    {
      title: "默认阈值",
      dataIndex: "default_threshold",
      width: 100,
      render: (v: number) => <span className="mono">{v.toFixed(2)}</span>,
    },
    {
      title: "综合分上线阈值",
      width: 160,
      render: (_: unknown, r: ReleaseThresholdItem) => (
        <InputNumber
          min={0.01}
          max={r.max_total}
          step={0.01}
          value={rt.draft[r.profile]}
          onChange={(v) => rt.setProfileDraft(r.profile, (v as number) ?? r.default_threshold)}
        />
      ),
    },
    {
      title: "状态",
      width: 110,
      render: (_: unknown, r: ReleaseThresholdItem) =>
        isCustomized(r, rt.draft) ? (
          <span className="status-dot status-dot--warn">已自定义</span>
        ) : (
          <span className="status-dot status-dot--muted">默认</span>
        ),
    },
    {
      title: "操作",
      width: 90,
      render: (_: unknown, r: ReleaseThresholdItem) => (
        <DashTableLink
          disabled={!isCustomized(r, rt.draft)}
          onClick={() => rt.resetProfile(r.profile, r.default_threshold)}
        >
          恢复默认
        </DashTableLink>
      ),
    },
  ];

  return (
    <DashboardPageShell
      title="上线判定阈值（按场景）"
      sub="按 score_profile 自定义综合分上线门槛；保存后对之后发起的新评测与重判生效"
      extra={
        <Button type="primary" loading={rt.saving} onClick={rt.save}>
          保存
        </Button>
      }
    >
      <div className="dash-table-card">
        <div className="dash-table-card__head">
          <h3>各评分档门槛</h3>
          <span className="dash-table-card__count">
            {customizedCount > 0 ? `已自定义 ${customizedCount} 项 · ` : ""}
            共 {rt.rows.length} 档
          </span>
        </div>
        {rt.loadError ? (
          <AsyncLoadError message={rt.loadError} onRetry={rt.reload} />
        ) : (
          <Table
            className="dash-table"
            rowKey="profile"
            size="small"
            loading={rt.loading}
            columns={columns}
            dataSource={rt.rows}
            pagination={false}
            rowClassName={(r) => (isCustomized(r, rt.draft) ? "dash-table__row--dirty" : "")}
          />
        )}
      </div>
    </DashboardPageShell>
  );
}
