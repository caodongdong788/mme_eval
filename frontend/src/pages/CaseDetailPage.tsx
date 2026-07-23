import { Button, Col, Empty, Result, Row, Spin } from "antd";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { CasePreviewRejudgePanel } from "../components/CasePreviewRejudgePanel";
import { EditCriteriaDrawer } from "../components/EditCriteriaDrawer";
import { CaseDetailSummary, CaseDetailSummaryCard } from "../components/CaseDetailSummaryCard";
import { ConversationContextReferences } from "../components/ConversationContextReferences";
import { CxReplayEmbed } from "../components/CxReplayEmbed";
import { DashPanel } from "../components/DashPanel";
import { HumanReviewCard } from "../components/HumanReviewCard";
import { JudgeVerdictTable } from "../components/JudgeVerdictTable";
import { GuidelineScoresTable } from "../components/GuidelineScoresTable";
import { AgentChainPanel } from "../components/AgentChainPanel";
import type { AgentChainTrace } from "../components/AgentChainPanel";
import { useFailureTagLabels } from "../hooks/useConfigLabelMap";
import { useCaseDetail } from "../hooks/useCaseDetail";
import { CaseVerdict } from "../utils/caseJudging";

export default function CaseDetailPage() {
  const { runId, sampleId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
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

  const trace = cd.detail.trace as (AgentChainTrace & {
    messages?: Array<{ role: string; content: string }>;
    cx_evaluation_share_url?: string | null;
  }) | undefined;
  const caseInfo = cd.detail.case as {
    sample_id?: string;
    scenario?: string;
    initial_state?: Record<string, unknown>;
    turns?: Array<{ role?: string; images?: string[] }>;
  } | undefined;
  let userTurnIndex = 0;
  const caseUserTurns = (caseInfo?.turns || []).filter((turn) => turn.role === "user");
  const messages = (trace?.messages || []).map((message) => {
    if (message.role !== "user") return message;
    const images = caseUserTurns[userTurnIndex++]?.images || [];
    return images.length ? { ...message, images } : message;
  });
  const verdicts = (cd.detail.verdicts as CaseVerdict[] | undefined) || [];
  const guidelineScores = (cd.detail.guideline_scores || []) as import("../api").GuidelineScore[];

  return (
    <div className="dash-page">
      <CaseDetailSummaryCard
        detail={cd.detail as CaseDetailSummary}
        backTo={backTo}
        backState={backState}
        backLabel={backLabel}
        retrying={cd.retrying}
        onRetry={cd.retryCase}
        nextSampleId={cd.nextSampleId}
        onNext={() => {
          if (!cd.nextSampleId) return;
          navigate(`/runs/${id}/cases/${cd.nextSampleId}`, {
            state: { from: { to: backTo, state: backState, label: backLabel } },
          });
        }}
      />

      <Row gutter={14}>
        <Col xs={24} lg={14}>
          <DashPanel
            title="CX 完整回放"
            extra={trace?.cx_evaluation_share_url ? (
              <Button type="link" size="small" href={trace.cx_evaluation_share_url} target="_blank" rel="noreferrer">
                在新窗口打开
              </Button>
            ) : undefined}
          >
            {trace?.cx_evaluation_share_url ? (
              <CxReplayEmbed
                src={trace.cx_evaluation_share_url}
                messages={messages}
                resolveImageSrc={(imagePath) =>
                  `/api/runs/${id}/cases/${encodeURIComponent(sampleId || "")}/images/${encodeURIComponent(imagePath)}`
                }
              />
            ) : (
              <Empty description="此用例尚未生成 CX 回放，请重新评测" />
            )}
          </DashPanel>
        </Col>
        <Col xs={24} lg={10}>
          <DashPanel title="对话引用的用户档案和过往事实">
            <ConversationContextReferences
              initialState={caseInfo?.initial_state}
              messages={messages}
            />
          </DashPanel>
        </Col>
      </Row>

      <AgentChainPanel
        trace={trace}
        syncing={cd.chainSyncing}
        onSync={cd.syncAgentChain}
        caseInitialState={caseInfo?.initial_state}
      />

      <JudgeVerdictTable
        verdicts={verdicts}
        tagLabel={tagLabel}
        dimensionRawScores={cd.detail.dimension_raw_scores as Record<string, number | null> | undefined}
        dimensionScores={cd.detail.dimension_scores as Record<string, number | null> | undefined}
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
