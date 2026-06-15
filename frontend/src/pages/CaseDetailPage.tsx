import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Modal,
  Result,
  Row,
  Space,
  message,
} from "antd";
import { Link, useLocation, useParams } from "react-router-dom";
import { Annotation, PreviewRejudgeResult, RunDetail, api } from "../api";
import { EditCriteriaDrawer } from "../components/EditCriteriaDrawer";
import { CaseDetailSummary, CaseDetailSummaryCard } from "../components/CaseDetailSummaryCard";
import { CaseDimensionScoresCard } from "../components/CaseDimensionScoresCard";
import { ConversationThread } from "../components/ConversationThread";
import { HumanReviewCard } from "../components/HumanReviewCard";
import { JudgeVerdictTable } from "../components/JudgeVerdictTable";
import { ScoringPointsTable } from "../components/ScoringPointsTable";
import { useFailureTagLabels } from "../failureTags";
import { formatApiError } from "../utils/apiError";
import { useBenchmarkYamlActions } from "../hooks/useBenchmarkYamlActions";
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
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [verdict, setVerdict] = useState<"agree" | "override">("agree");
  const [suggestion, setSuggestion] = useState("");
  const [comment, setComment] = useState("");
  const [saving, setSaving] = useState(false);

  const [run, setRun] = useState<RunDetail | null>(null);
  const [benchmarkName, setBenchmarkName] = useState<string | undefined>();
  const [isBuiltin, setIsBuiltin] = useState(false);
  const [yamlOpen, setYamlOpen] = useState(false);
  const [yamlLoading, setYamlLoading] = useState(false);
  const [yamlText, setYamlText] = useState("");
  const [yamlName, setYamlName] = useState("");
  const [previewing, setPreviewing] = useState(false);
  const [previewResult, setPreviewResult] = useState<PreviewRejudgeResult | null>(null);
  const yamlActions = useBenchmarkYamlActions({
    benchmarkId: run?.benchmark_id,
    getYamlText: () => yamlText,
  });

  const loadAnnotations = () => {
    if (sampleId) api.getCaseAnnotations(id, sampleId).then(setAnnotations);
  };

  useEffect(() => {
    if (sampleId) {
      setDetailError(null);
      api
        .getCaseDetail(id, sampleId)
        .then(setDetail)
        .catch((e) => setDetailError(formatApiError(e, "加载用例明细失败")));
    }
    loadAnnotations();
    Promise.all([api.getRun(id), api.listBenchmarks()])
      .then(([r, list]) => {
        setRun(r);
        const bm = list.find((b) => b.id === r.benchmark_id);
        setBenchmarkName(bm?.name);
        setIsBuiltin(bm?.source === "builtin");
      })
      .catch(() => {});
  }, [id, sampleId]);

  const submitAnnotation = async () => {
    if (!sampleId) return;
    setSaving(true);
    try {
      await api.annotateCase(id, sampleId, {
        verdict,
        suggestion: suggestion.trim() || undefined,
        comment: comment.trim() || undefined,
      });
      message.success("裁定已记录（不影响机器判分）");
      setSuggestion("");
      setComment("");
      loadAnnotations();
    } catch (e: unknown) {
      message.error(formatApiError(e, "提交失败"));
    } finally {
      setSaving(false);
    }
  };

  const openEditor = async () => {
    if (!sampleId) return;
    setYamlOpen(true);
    setYamlLoading(true);
    setYamlText("");
    setPreviewResult(null);
    try {
      const res = await api.getRunCasesYaml(id, { sample_id: sampleId });
      setYamlText(res.yaml_text);
      setYamlName(
        `${run?.name || "派生"} · 改判据 ${new Date()
          .toISOString()
          .slice(5, 16)
          .replace("T", "-")}`
      );
    } catch (e: unknown) {
      message.error(formatApiError(e, "加载用例 YAML 失败"));
      setYamlOpen(false);
    } finally {
      setYamlLoading(false);
    }
  };

  const runPreview = async () => {
    if (!sampleId) return;
    setPreviewing(true);
    try {
      const res = await api.previewRejudgeCase(id, sampleId, { yaml_text: yamlText });
      setPreviewResult(res);
    } catch (e: unknown) {
      message.error(formatApiError(e, "试判失败"));
    } finally {
      setPreviewing(false);
    }
  };

  const saveYamlAsBenchmark = () =>
    yamlActions.saveAsBenchmark({
      name: yamlName,
      description: `从 #${run?.benchmark_id} 改判据派生（用例 ${sampleId}）`,
      onSuccess: (bm) => {
        setYamlOpen(false);
        Modal.success({
          title: "已另存为新 benchmark",
          content: `新 benchmark #${bm.id}「${bm.name}」已创建。可在看板「重判」里选它发起重判。`,
        });
      },
    });

  const saveYamlOverwrite = () =>
    yamlActions.overwriteBenchmark({
      confirmContent:
        "将用编辑后的判据就地覆盖这次评测当前关联的 benchmark（按 sample_id 只合并判据字段）。" +
        "此操作仅更新判据源、不改当前 run 已存分；要让某个 run 反映新判据需另行「重判」。不可撤销。",
      onSuccess: (bm) => {
        setYamlOpen(false);
        Modal.success({
          title: "已覆盖当前 benchmark",
          content: `benchmark #${bm.id}「${bm.name}」判据已更新。要让评测反映新判据，请到看板「重判」。`,
        });
      },
    });

  if (detailError)
    return (
      <Result
        status="warning"
        title="无法加载用例明细"
        subTitle={detailError}
        extra={
          <Link to={backTo} state={backState}>
            <Button>返回{backLabel}</Button>
          </Link>
        }
      />
    );
  if (!detail) return <Card loading />;

  const trace = detail.trace as { messages?: Array<{ role: string; content: string }>; langfuse_trace_url?: string } | undefined;
  const messages = trace?.messages || [];
  const verdicts = (detail.verdicts as CaseVerdict[] | undefined) || [];
  const scoringPoints = verdicts.filter((v) => v.name?.startsWith("scoring_point."));
  const mainVerdicts = verdicts.filter((v) => !v.name?.startsWith("scoring_point."));
  const caseInfo = detail.case as { sample_id?: string; sub_scenario?: string; scenario?: string } | undefined;

  return (
    <Space direction="vertical" size={16} style={{ display: "flex" }}>
      <CaseDetailSummaryCard
        detail={detail as CaseDetailSummary}
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
            dimensionScores={detail.dimension_scores as Record<string, number | null> | undefined}
            dimensionMax={detail.dimension_max as Record<string, number> | undefined}
            scoreDeductions={detail.score_deductions as string[] | undefined}
            highlightKeywords={detail.highlight_keywords as string[] | undefined}
          />
        </Col>
      </Row>

      <JudgeVerdictTable verdicts={mainVerdicts} tagLabel={tagLabel} />
      <ScoringPointsTable scoringPoints={scoringPoints} />

      <HumanReviewCard
        verdict={verdict}
        onVerdictChange={setVerdict}
        suggestion={suggestion}
        onSuggestionChange={setSuggestion}
        comment={comment}
        onCommentChange={setComment}
        saving={saving}
        onSubmit={submitAnnotation}
        onOpenEditor={openEditor}
        annotations={annotations}
      />

      <EditCriteriaDrawer
        open={yamlOpen}
        loading={yamlActions.saving}
        isBuiltin={isBuiltin}
        hideAlert
        hideSaveAs
        benchmarkLabel={
          run?.benchmark_id
            ? `#${run.benchmark_id}「${benchmarkName || "—"}」`
            : undefined
        }
        title={`改判据 · ${caseInfo?.sub_scenario || caseInfo?.scenario || sampleId}`}
        name={yamlName}
        onNameChange={setYamlName}
        yamlText={yamlText}
        onYamlChange={setYamlText}
        yamlLoading={yamlLoading}
        onClose={() => setYamlOpen(false)}
        onSaveAs={saveYamlAsBenchmark}
        onOverwrite={saveYamlOverwrite}
        slot={
          <Space direction="vertical" size={10} style={{ width: "100%" }}>
            <Button
              type="primary"
              size="large"
              block
              loading={previewing}
              onClick={runPreview}
              disabled={yamlLoading || !yamlText}
            >
              试判此用例（预览）
            </Button>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              用编辑后的判据跑一次试判，仅预览、不修改当前 run；满意后点右上「覆盖当前 benchmark」。
            </span>
            {previewResult && (
              <Alert
                type={previewResult.changed ? "warning" : "success"}
                showIcon
                message={
                  previewResult.changed ? "试判结果与当前不同" : "试判结果与当前一致"
                }
                description={
                  <Space direction="vertical" size={8} style={{ width: "100%", marginTop: 4 }}>
                    <Descriptions column={1} size="small">
                      <Descriptions.Item label="上线判定">
                        {previewResult.current.release_passed ? "通过" : "失败"}
                        {" → "}
                        {previewResult.preview.release_passed ? (
                          <span className="status-dot status-dot--pass">通过</span>
                        ) : (
                          <span className="status-dot status-dot--fail">失败</span>
                        )}
                      </Descriptions.Item>
                      <Descriptions.Item label="综合分">
                        {previewResult.current.composite_score?.toFixed?.(2) ?? "-"}
                        {" → "}
                        {previewResult.preview.composite_score?.toFixed?.(2) ?? "-"}
                      </Descriptions.Item>
                      <Descriptions.Item label="评级">
                        {previewResult.current.grade || "-"}
                        {" → "}
                        {previewResult.preview.grade || "-"}
                      </Descriptions.Item>
                      <Descriptions.Item label="硬门槛">
                        {previewResult.current.hard_gate_passed ? "通过" : "失败"}
                        {" → "}
                        {previewResult.preview.hard_gate_passed ? "通过" : "失败"}
                      </Descriptions.Item>
                    </Descriptions>
                    <div>
                      <strong style={{ fontSize: 12 }}>本次扣分项</strong>
                      {previewResult.preview.score_deductions.length === 0 ? (
                        <span style={{ fontSize: 12, marginLeft: 8, color: "var(--muted)" }}>
                          无扣分
                        </span>
                      ) : (
                        <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                          {previewResult.preview.score_deductions.map((d, i) => (
                            <li key={i} style={{ fontSize: 12 }}>
                              {d}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </Space>
                }
              />
            )}
          </Space>
        }
      />
    </Space>
  );
}
