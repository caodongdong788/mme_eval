import { Button, Card, Col, Result, Row, Space } from "antd";
import { Link, useLocation, useParams } from "react-router-dom";
import { CasePreviewRejudgePanel } from "../components/CasePreviewRejudgePanel";
import { EditCriteriaDrawer } from "../components/EditCriteriaDrawer";
import { CaseDetailSummary, CaseDetailSummaryCard } from "../components/CaseDetailSummaryCard";
import { CaseDimensionScoresCard } from "../components/CaseDimensionScoresCard";
import { ConversationThread } from "../components/ConversationThread";
import { HumanReviewCard } from "../components/HumanReviewCard";
import { JudgeVerdictTable } from "../components/JudgeVerdictTable";
import { ScoringPointsTable } from "../components/ScoringPointsTable";
import { useFailureTagLabels } from "../failureTags";
import { useCaseDetail } from "../hooks/useCaseDetail";
import { CaseVerdict } from "../utils/caseJudging";

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
      <Result
        status="warning"
        title="无法加载用例明细"
        subTitle={cd.detailError}
        extra={
          <Link to={backTo} state={backState}>
            <Button>返回{backLabel}</Button>
          </Link>
        }
      />
    );
  }
  if (!cd.detail) return <Card loading />;

  const trace = cd.detail.trace as { messages?: Array<{ role: string; content: string }> } | undefined;
  const messages = trace?.messages || [];
  const verdicts = (cd.detail.verdicts as CaseVerdict[] | undefined) || [];
  const scoringPoints = verdicts.filter((v) => v.name?.startsWith("scoring_point."));
  const mainVerdicts = verdicts.filter((v) => !v.name?.startsWith("scoring_point."));
  const caseInfo = cd.detail.case as { sample_id?: string; sub_scenario?: string; scenario?: string } | undefined;

  return (
    <Space direction="vertical" size={16} style={{ display: "flex" }}>
      <CaseDetailSummaryCard
        detail={cd.detail as CaseDetailSummary}
        scoringPoints={scoringPoints}
        backTo={backTo}
        backState={backState}
        backLabel={backLabel}
      />

      <Row gutter={16}>
        <Col span={14}>
          <Card title="对话流水" size="small">
            <ConversationThread messages={messages} />
          </Card>
        </Col>
        <Col span={10}>
          <CaseDimensionScoresCard
            dimensionScores={cd.detail.dimension_scores as Record<string, number | null> | undefined}
            dimensionMax={cd.detail.dimension_max as Record<string, number> | undefined}
            scoreDeductions={cd.detail.score_deductions as string[] | undefined}
            highlightKeywords={cd.detail.highlight_keywords as string[] | undefined}
          />
        </Col>
      </Row>

      <JudgeVerdictTable verdicts={mainVerdicts} tagLabel={tagLabel} />
      <ScoringPointsTable scoringPoints={scoringPoints} />

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
        title={`改判据 · ${caseInfo?.sub_scenario || caseInfo?.scenario || sampleId}`}
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
    </Space>
  );
}
