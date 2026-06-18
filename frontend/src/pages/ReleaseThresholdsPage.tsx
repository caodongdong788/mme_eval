import { Alert, Button, Tabs, Tooltip } from "antd";
import { QuestionCircleOutlined } from "@ant-design/icons";
import { ScoringProfileForm } from "../components/ScoringProfileForm";
import { AsyncLoadError } from "../components/AsyncLoadError";
import { DashboardPageShell } from "../components/DashboardPageShell";
import { isProfileCustomized, useScoringProfilesPage } from "../hooks/useScoringProfilesPage";
import { PROFILE_LABEL } from "../labels";

const PAGE_TIP =
  "每道题按用例 score_profile 归入一个场景。此处调整的是报告层合成综合分与上线判定口径，不改变 HardGate / Rule / LLM 判分逻辑。历史 run 以 config_snapshot 为准。";

export default function ReleaseThresholdsPage() {
  const sp = useScoringProfilesPage();

  const tabItems = sp.rows.map((row) => {
    const customized =
      sp.draft[row.profile] && isProfileCustomized(row, sp.draft[row.profile]);
    return {
      key: row.profile,
      label: (
        <span className="dash-scoring-tab">
          <span className="dash-scoring-tab__name">
            {PROFILE_LABEL[row.profile] ?? row.label}
            {customized ? <span className="dash-scoring-tab__mark" title="已自定义">*</span> : null}
          </span>
          {row.coverage.case_count > 0 ? (
            <span className="dash-scoring-tab__meta">{row.coverage.case_count} 题</span>
          ) : null}
        </span>
      ),
    };
  });

  const activeRow = sp.rows.find((r) => r.profile === sp.activeProfile);

  return (
    <DashboardPageShell
      title="评分配置"
      sub="按评测场景调整模块权重、功能扣分与上线门槛"
      extra={
        <Button type="primary" loading={sp.saving} onClick={sp.save}>
          保存
        </Button>
      }
    >
      <div className="dash-scoring-config">
        <Alert
          type="info"
          showIcon
          className="dash-scoring-config__alert"
          message={
            <span>
              配置说明{" "}
              <Tooltip title={PAGE_TIP}>
                <QuestionCircleOutlined />
              </Tooltip>
            </span>
          }
          description="保存后仅对之后发起的新评测与重判生效；历史报告不可追溯修改。"
        />
        {sp.loadError ? (
          <AsyncLoadError message={sp.loadError} onRetry={sp.reload} />
        ) : (
          <div className="dash-scoring-card">
            <div className="dash-scoring-card__head">
              <h3>评分场景</h3>
              <span className="dash-scoring-card__count">
                {sp.customizedCount > 0 ? `已自定义 ${sp.customizedCount} · ` : ""}
                共 {sp.rows.length} 档
              </span>
            </div>
            <Tabs
              className="dash-tabs dash-scoring-tabs"
              activeKey={sp.activeProfile}
              onChange={sp.setActiveProfile}
              items={tabItems}
            />
            <div className="dash-scoring-card__body">
              {activeRow && sp.draft[activeRow.profile] ? (
                <ScoringProfileForm
                  row={activeRow}
                  draft={sp.draft[activeRow.profile]}
                  setProfileDraft={sp.setProfileDraft}
                  resetProfile={sp.resetProfile}
                />
              ) : null}
            </div>
          </div>
        )}
      </div>
    </DashboardPageShell>
  );
}
