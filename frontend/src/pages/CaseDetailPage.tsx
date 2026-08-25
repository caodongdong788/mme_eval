import { Button, Col, Result, Row, Spin } from "antd";
import { useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { BenchmarkCaseEditorDrawer } from "../components/BenchmarkCaseEditorDrawer";
import { CasePreviewRejudgePanel } from "../components/CasePreviewRejudgePanel";
import { CaseDetailSummary, CaseDetailSummaryCard } from "../components/CaseDetailSummaryCard";
import { ConversationContextReferences } from "../components/ConversationContextReferences";
import { CxReplayEmbed } from "../components/CxReplayEmbed";
import { DashPanel } from "../components/DashPanel";
import { HumanReviewCard } from "../components/HumanReviewCard";
import { JudgeVerdictTable, type AssertionScore } from "../components/JudgeVerdictTable";
import { GuidelineScoresTable } from "../components/GuidelineScoresTable";
import { AgentChainPanel } from "../components/AgentChainPanel";
import { SimulationTracePanel } from "../components/SimulationTracePanel";
import type { AgentChainTrace, CaseEvaluationAssertion } from "../components/AgentChainPanel";
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
  const backTo = backFrom?.to ?? `/runs/${id}?tab=detail`;
  const backState = backFrom?.state;
  const backLabel = backFrom?.label ?? "用例列表";

  const cd = useCaseDetail(id, sampleId);
  const [cxReplayFallback, setCxReplayFallback] = useState(false);

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
    simulation_trace?: Array<{ turn?: number; source?: string; id?: string; content?: string; facts_added?: Record<string, unknown> }>;
  }) | undefined;
  const caseInfo = cd.detail.case as {
    sample_id?: string;
    scenario?: string;
    initial_state?: Record<string, unknown>;
    turns?: Array<{ role?: string; images?: string[] }>;
    evaluation?: Record<string, unknown>;
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
  const assertionScores = (cd.detail.assertion_scores || []) as AssertionScore[];
  const assertions = Array.isArray(caseInfo?.evaluation?.assertions)
    ? caseInfo.evaluation.assertions as CaseEvaluationAssertion[]
    : [];
  const assertionVerdicts = verdicts.filter((verdict) => verdict.name.startsWith("assertion."));

  return (
    <div className="dash-page">
      <CaseDetailSummaryCard
        detail={cd.detail as CaseDetailSummary}
        backTo={backTo}
        backState={backState}
        backLabel={backLabel}
        retrying={cd.retrying}
        retryProgress={cd.retryProgress}
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
            title={trace?.cx_evaluation_share_url ? (
              <div className="cx-replay-panel-title">
                <h3>CX 完整回放</h3>
                {cxReplayFallback && (
                  <span className="cx-replay-panel-title__hint">
                    CX 原生回放暂不可嵌入，已切换为本地回放
                  </span>
                )}
              </div>
            ) : "对话明细"}
            extra={trace?.cx_evaluation_share_url ? (
              <Button type="link" size="small" href={trace.cx_evaluation_share_url} target="_blank" rel="noreferrer">
                在新窗口打开
              </Button>
            ) : undefined}
          >
            <CxReplayEmbed
              src={trace?.cx_evaluation_share_url}
              messages={messages}
              onFallbackChange={setCxReplayFallback}
              resolveImageSrc={(imagePath) =>
                `/api/runs/${id}/cases/${encodeURIComponent(sampleId || "")}/images/${encodeURIComponent(imagePath)}`
              }
            />
          </DashPanel>
        </Col>
        <Col xs={24} lg={10}>
          <DashPanel title="本次用例初始化数据与回答引用">
            <ConversationContextReferences
              initialState={trace?.evaluation_identity?.initial_state ?? caseInfo?.initial_state}
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
        loadRagAudit={cd.loadRagAudit}
        assertions={assertions}
        assertionVerdicts={assertionVerdicts}
        scoringStandard={cd.run?.scoring_standard}
      />

      <SimulationTracePanel events={trace?.simulation_trace} />

      <JudgeVerdictTable
        verdicts={verdicts}
        tagLabel={tagLabel}
        dimensionRawScores={cd.detail.dimension_raw_scores as Record<string, number | null> | undefined}
        dimensionScores={cd.detail.dimension_scores as Record<string, number | null> | undefined}
        dimensionMax={cd.detail.dimension_max as Record<string, number> | undefined}
        scoreDeductions={cd.detail.score_deductions as string[] | undefined}
        guidelineScores={guidelineScores}
        assertionScores={assertionScores}
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

      <BenchmarkCaseEditorDrawer
        open={cd.criteriaOpen}
        loading={cd.criteriaLoading}
        saving={cd.criteriaSaving}
        source={cd.isBuiltin ? "builtin" : "uploaded"}
        caseFile={cd.caseContent?.case_file}
        value={cd.caseContent?.case || null}
        onChange={(nextCase) =>
          cd.setCaseContent((current) => current ? { ...current, case: nextCase } : current)
        }
        onClose={() => cd.setCriteriaOpen(false)}
        variant="criteria"
        isBuiltin={cd.isBuiltin}
        benchmarkLabel={
          cd.run?.benchmark_id
            ? `#${cd.run.benchmark_id}「${cd.benchmarkName || "—"}」`
            : undefined
        }
        title={`改判据 · ${caseInfo?.scenario || sampleId}`}
        subtitle="Benchmark 结构化编辑"
        saveHint="覆盖后将更新当前 benchmark；当前 run 分数不会自动变化"
        onOverwrite={cd.saveCaseOverwrite}
        headerContent={
          <CasePreviewRejudgePanel
            previewing={cd.previewing}
            editorLoading={cd.criteriaLoading}
            canPreview={Boolean(cd.caseContent)}
            previewResult={cd.previewResult}
            onPreview={cd.runPreview}
          />
        }
      />
    </div>
  );
}
