import { useEffect, useMemo, useState } from "react";
import { Button, Descriptions, Empty, Result, Spin, Tag } from "antd";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type AttributionTask, type CaseAttribution } from "../api";
import { AttributionDetail, type AttributionSafetyContext } from "../components/RunAttributionTab";
import { DashPanel } from "../components/DashPanel";
import { formatApiError } from "../utils/apiError";
import { formatApiDateTime } from "../utils/datetime";

export default function AttributionCaseDetailPage() {
  const { runId, taskId, sampleId } = useParams();
  const navigate = useNavigate();
  const runNumber = Number(runId);
  const taskNumber = Number(taskId);
  const decodedSampleId = useMemo(() => decodeURIComponent(sampleId || ""), [sampleId]);
  const [task, setTask] = useState<AttributionTask | null>(null);
  const [result, setResult] = useState<CaseAttribution | null>(null);
  const [safetyContext, setSafetyContext] = useState<AttributionSafetyContext>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    let alive = true;
    setError(undefined);
    Promise.all([
      api.getAttributionTask(runNumber, taskNumber),
      api.getAttributionTaskResult(runNumber, taskNumber, decodedSampleId),
      api.getCaseDetail(runNumber, decodedSampleId).catch(() => null),
    ]).then(([nextTask, nextResult, caseDetail]) => {
      if (!alive) return;
      setTask(nextTask);
      setResult(nextResult);
      const safetyVerdict = caseDetail?.verdicts?.find((verdict: { name?: string }) => verdict.name === "dimension.medical_safety");
      const safetyGuidelines = (caseDetail?.guideline_scores || []).filter((guideline: { dimension?: string; deduction?: number; score?: number; max_score?: number; applicable?: boolean }) => {
        if (guideline.dimension !== "medical_safety" || guideline.applicable === false) return false;
        const deduction = typeof guideline.deduction === "number"
          ? guideline.deduction
          : Math.max(0, Number(guideline.max_score || 0) - Number(guideline.score || 0));
        return deduction > 0;
      });
      setSafetyContext({
        gatePassed: typeof caseDetail?.medical_safety_passed === "boolean" ? caseDetail.medical_safety_passed : undefined,
        dimensionScore: typeof safetyVerdict?.score === "number" ? safetyVerdict.score : null,
        dimensionMax: typeof safetyVerdict?.max_score === "number" ? safetyVerdict.max_score : null,
        dimensionReason: safetyVerdict?.reason || undefined,
        guidelineDeductionCount: safetyGuidelines.length,
      });
    }).catch((reason) => {
      if (alive) setError(formatApiError(reason, "加载归因结果失败"));
    });
    return () => { alive = false; };
  }, [decodedSampleId, runNumber, taskNumber]);

  const item = task?.items.find((candidate) => candidate.sample_id === decodedSampleId);
  const returnState = { tab: "attribution", attributionTaskId: taskNumber };

  if (error) {
    return <div className="dash-page"><Result status="warning" title="无法加载归因结果" subTitle={error} extra={<Link to={`/runs/${runNumber}`} state={returnState}>返回归因任务</Link>} /></div>;
  }
  if (!task || !result) {
    return <div className="dash-page attribution-result-page attribution-result-page--loading"><Spin size="large" /></div>;
  }

  return (
    <div className="dash-page attribution-result-page">
      <DashPanel
        title={<Link to={`/runs/${runNumber}`} state={returnState} className="dash-table__link">← 返回归因任务</Link>}
        extra={<Button onClick={() => navigate(`/runs/${runNumber}/cases/${encodeURIComponent(decodedSampleId)}`, { state: { from: { to: `/runs/${runNumber}/attribution-tasks/${taskNumber}/cases/${encodeURIComponent(decodedSampleId)}`, label: "归因结果" } } })}>查看原用例</Button>}
      >
        <Descriptions title={`${decodedSampleId} · 归因结果`} column={{ xs: 1, md: 2, lg: 4 }} size="small">
          <Descriptions.Item label="归因任务">#{task.id}</Descriptions.Item>
          <Descriptions.Item label="分析模型">{task.judge_model_name || `模型 #${task.judge_model_id}`}</Descriptions.Item>
          <Descriptions.Item label="场景">{item?.scenario || "—"}</Descriptions.Item>
          <Descriptions.Item label="类别">{item?.case_type || "—"}</Descriptions.Item>
          <Descriptions.Item label="状态"><Tag color="success">已完成</Tag></Descriptions.Item>
          <Descriptions.Item label="创建时间">{formatApiDateTime(task.created_at)}</Descriptions.Item>
        </Descriptions>
      </DashPanel>

      {result.available ? (
        <DashPanel title="归因结论与优化建议">
          <AttributionDetail result={result} safetyContext={safetyContext} />
        </DashPanel>
      ) : (
        <DashPanel title="归因结论与优化建议"><Empty description="该用例暂无可查看的归因结果" /></DashPanel>
      )}
    </div>
  );
}
