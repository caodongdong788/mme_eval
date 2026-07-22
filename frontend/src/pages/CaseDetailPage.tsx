import { Col, Result, Row, Spin } from "antd";
import { Link, useLocation, useParams } from "react-router-dom";
import { CasePreviewRejudgePanel } from "../components/CasePreviewRejudgePanel";
import { EditCriteriaDrawer } from "../components/EditCriteriaDrawer";
import { CaseDetailSummary, CaseDetailSummaryCard } from "../components/CaseDetailSummaryCard";
import { ConversationThread } from "../components/ConversationThread";
import { DashPanel } from "../components/DashPanel";
import { HumanReviewCard } from "../components/HumanReviewCard";
import { JudgeVerdictTable } from "../components/JudgeVerdictTable";
import { GuidelineScoresTable } from "../components/GuidelineScoresTable";
import { AgentChainPanel } from "../components/AgentChainPanel";
import type { AgentChainTrace } from "../components/AgentChainPanel";
import { UserProfileBlock } from "../components/UserProfileBlock";
import { useFailureTagLabels } from "../hooks/useConfigLabelMap";
import { useCaseDetail } from "../hooks/useCaseDetail";
import { CaseVerdict } from "../utils/caseJudging";

const profileLabels: Record<string, string> = {
  nickname: "昵称",
  birthday: "出生日期",
  gender: "性别",
  currentConcern: "当前关注",
  medical: "医疗档案",
};

function profileHasContent(value: unknown): boolean {
  if (value === null || value === undefined || value === "") return false;
  if (Array.isArray(value)) return value.some(profileHasContent);
  if (typeof value === "object") return Object.values(value as Record<string, unknown>).some(profileHasContent);
  return true;
}

function profileValueText(value: unknown): string {
  if (Array.isArray(value)) return value.map(profileValueText).filter(Boolean).join("、");
  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .filter(([, item]) => profileHasContent(item))
      .map(([key, item]) => `${profileLabels[key] || key}：${profileValueText(item)}`)
      .join("；");
  }
  return value == null ? "" : String(value);
}

function profileText(profile: Record<string, unknown> | undefined): string {
  if (!profile || !profileHasContent(profile)) return "";
  return Object.entries(profile)
    .filter(([, value]) => profileHasContent(value))
    .map(([key, value]) => `${profileLabels[key] || key}：${profileValueText(value)}`)
    .join("\n");
}

export default function CaseDetailPage() {
  const { runId, sampleId } = useParams();
  const location = useLocation();
  const tagLabel = useFailureTagLabels();
  const id = Number(runId);
  const backFrom = (location.state as { from?: { to: string; state?: unknown; label?: string } } | null)?.from;
  const backTo = backFrom?.to ?? `/runs/${id}`;
  const backState = backFrom?.state ?? { tab: "detail" };
  const backLabel = backFrom?.label ?? "用例列表";

  const cd = useCaseDetail(id, sampleId);

  if (cd.detailError) {
    return (
      <div className="dash-page">
        <Result
          status="warning"
          title="无法加载用例明细"
          subTitle={cd.detailError}
          extra={
            <Link to={backTo} state={backState} className="dash-table__link">
              返回{backLabel}
            </Link>
          }
        />
      </div>
    );
  }
  if (!cd.detail) {
    return (
      <div className="dash-page" style={{ display: "grid", placeItems: "center", paddingTop: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  const trace = cd.detail.trace as (AgentChainTrace & { messages?: Array<{ role: string; content: string }> }) | undefined;
  const caseInfo = cd.detail.case as { sample_id?: string; scenario?: string; turns?: Array<{ role?: string; images?: string[] }> } | undefined;
  let userTurnIndex = 0;
  const caseUserTurns = (caseInfo?.turns || []).filter((turn) => turn.role === "user");
  const messages = (trace?.messages || []).map((message) => {
    if (message.role !== "user") return message;
    const images = caseUserTurns[userTurnIndex++]?.images || [];
    return images.length ? { ...message, images } : message;
  });
  const verdicts = (cd.detail.verdicts as CaseVerdict[] | undefined) || [];
  const guidelineScores = (cd.detail.guideline_scores || []) as import("../api").GuidelineScore[];
  const identityProfile = trace?.evaluation_identity?.user_profile || trace?.evaluation_identity?.profile_after_reset;
  const userProfileText = profileText(identityProfile);

  return (
    <div className="dash-page">
      <CaseDetailSummaryCard
        detail={cd.detail as CaseDetailSummary}
        backTo={backTo}
        backState={backState}
        backLabel={backLabel}
        retrying={cd.retrying}
        onRetry={cd.retryCase}
      />

      <Row gutter={14}>
        <Col xs={24} lg={userProfileText ? 16 : 24}>
          <DashPanel title="对话流水">
            <ConversationThread
              messages={messages}
              resolveImageSrc={(imagePath) =>
                `/api/runs/${id}/cases/${encodeURIComponent(sampleId || "")}/images/${encodeURIComponent(imagePath)}`
              }
            />
          </DashPanel>
        </Col>
        {userProfileText ? (
          <Col xs={24} lg={8}>
            <DashPanel title="用户画像">
              <UserProfileBlock text={userProfileText} showTitle={false} />
            </DashPanel>
          </Col>
        ) : null}
      </Row>

      <AgentChainPanel
        trace={trace}
        syncing={cd.chainSyncing}
        onSync={cd.syncAgentChain}
      />

      <JudgeVerdictTable
        verdicts={verdicts}
        tagLabel={tagLabel}
        dimensionScores={cd.detail.dimension_scores as Record<string, number | null> | undefined}
        dimensionRawScores={cd.detail.dimension_raw_scores as Record<string, number | null> | undefined}
        dimensionMax={cd.detail.dimension_max as Record<string, number> | undefined}
        scoreDeductions={cd.detail.score_deductions as string[] | undefined}
      />
      <GuidelineScoresTable scores={guidelineScores} />

      <HumanReviewCard
        verdict={cd.verdict}
        onVerdictChange={cd.setVerdict}
        suggestion={cd.suggestion}
        onSuggestionChange={cd.setSuggestion}
        comment={cd.comment}
        onCommentChange={cd.setComment}
        saving={cd.saving}
        onSubmit={cd.submitAnnotation}
        onOpenEditor={cd.openEditor}
        annotations={cd.annotations}
      />

      <EditCriteriaDrawer
        open={cd.yamlOpen}
        loading={cd.yamlActions.saving}
        isBuiltin={cd.isBuiltin}
        hideAlert
        hideSaveAs
        benchmarkLabel={
          cd.run?.benchmark_id
            ? `#${cd.run.benchmark_id}「${cd.benchmarkName || "—"}」`
            : undefined
        }
        title={`改判据 · ${caseInfo?.scenario || sampleId}`}
        name={cd.yamlName}
        onNameChange={cd.setYamlName}
        yamlText={cd.yamlText}
        onYamlChange={cd.setYamlText}
        yamlLoading={cd.yamlLoading}
        onClose={() => cd.setYamlOpen(false)}
        onSaveAs={cd.saveYamlAsBenchmark}
        onOverwrite={cd.saveYamlOverwrite}
        slot={
          <CasePreviewRejudgePanel
            previewing={cd.previewing}
            yamlLoading={cd.yamlLoading}
            yamlText={cd.yamlText}
            previewResult={cd.previewResult}
            onPreview={cd.runPreview}
          />
        }
      />
    </div>
  );
}
