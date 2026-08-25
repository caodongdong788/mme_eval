import { Alert, Button, Descriptions, Progress, Space } from "antd";
import { Link } from "react-router-dom";
import type { GuidelineScore, ProgressInfo } from "../api";
import { STABILITY_LABEL } from "../labels";
import { DashPanel } from "./DashPanel";

export interface CaseDetailSummary {
  case?: { sample_id?: string; scenario?: string; level?: string };
  composite_score?: number;
  grade?: string;
  stability?: string;
  medical_safety_passed?: boolean | null;
  release_passed?: boolean;
  end_scores?: Record<string, number>;
  guideline_scores?: GuidelineScore[];
  dimension_max?: Record<string, number>;
  trace?: { langfuse_trace_url?: string | null; error?: string | null };
}

function executionFailureMessage(error?: string | null) {
  if (!error) return "执行链路未返回 Agent 回答。";
  if (error.includes("account lease")) {
    return "评测账号初始化失败，尚未发送对话请求，因此没有 Agent 回复。";
  }
  return "执行链路在产生 Agent 回答前失败，因此没有可评分的对话结果。";
}

export function CaseDetailSummaryCard({
  detail,
  backTo,
  backState,
  backLabel,
  retrying = false,
  retryProgress,
  onRetry,
  nextSampleId,
  onNext,
}: {
  detail: CaseDetailSummary;
  backTo: string;
  backState?: unknown;
  backLabel: string;
  retrying?: boolean;
  retryProgress?: ProgressInfo | null;
  onRetry?: () => void;
  nextSampleId?: string;
  onNext?: () => void;
}) {
  const earned = (detail.guideline_scores || []).reduce((sum, item) => sum + item.score, 0);
  const maximum = (detail.guideline_scores || []).reduce((sum, item) => sum + item.max_score, 0);
  const progress = retryProgress?.progress;
  const retryPercent = Math.min(100, Math.max(0, progress?.percent ?? 0));
  const retryLabel = progress?.current_label || "等待开始重试";
  const retryCount = progress?.total ? `${progress.done ?? 0}/${progress.total}` : "准备中";
  const executionError = detail.trace?.error?.trim();
  return (
    <DashPanel
      title={<Link to={backTo} state={backState} className="dash-table__link">← 返回{backLabel}</Link>}
      extra={
        onRetry ? (
          <Space size={12}>
            <Button disabled={!nextSampleId || retrying} onClick={onNext}>
              下一题
            </Button>
            <Button type="primary" loading={retrying} onClick={onRetry}>重试此 Case</Button>
          </Space>
        ) : undefined
      }
    >
      <Descriptions title={`用例 ${detail.case?.sample_id}`} column={3} size="small">
        <Descriptions.Item label="场景">{detail.case?.scenario}</Descriptions.Item>
        <Descriptions.Item label="Level">{detail.case?.level}</Descriptions.Item>
        <Descriptions.Item label="总分">
          {executionError ? "未评分" : `${detail.composite_score ?? "-"}/${Object.values(detail.dimension_max || {}).reduce((sum, value) => sum + Number(value || 0), 0) || 40}`}
        </Descriptions.Item>
        {!executionError && detail.end_scores && Object.keys(detail.end_scores).length ? <>
          <Descriptions.Item label="医生端">{detail.end_scores.doctor ?? "-"}/15</Descriptions.Item>
          <Descriptions.Item label="护士端">{detail.end_scores.nurse ?? "-"}/10</Descriptions.Item>
          <Descriptions.Item label="患者端">{detail.end_scores.user ?? "-"}/15</Descriptions.Item>
        </> : null}
        <Descriptions.Item label="质量评级">{executionError ? "执行失败" : detail.grade || "-"}</Descriptions.Item>
        <Descriptions.Item label="稳定性">{STABILITY_LABEL[detail.stability || ""] || detail.stability || "-"}</Descriptions.Item>
        <Descriptions.Item label="医学安全性">
          {executionError ? "未评测" : detail.medical_safety_passed == null ? "不适用" : detail.medical_safety_passed ? "通过" : "失败"}
        </Descriptions.Item>
        <Descriptions.Item label="运行验收">
          <span className={`status-dot status-dot--${executionError ? "fail" : detail.release_passed ? "pass" : "fail"}`}>
            {executionError ? "执行失败" : detail.release_passed ? "合格" : "不合格"}
          </span>
        </Descriptions.Item>
        <Descriptions.Item label="指南得分">{executionError ? "未评测" : maximum ? `${earned}/${maximum}` : "无指南项"}</Descriptions.Item>
        {detail.trace?.langfuse_trace_url ? (
          <Descriptions.Item label="追踪链路"><a href={detail.trace.langfuse_trace_url} target="_blank" rel="noreferrer">在 Langfuse 查看</a></Descriptions.Item>
        ) : null}
      </Descriptions>
      {executionError ? (
        <Alert
          type="error"
          showIcon
          message="未产生 Agent 回答"
          description={executionFailureMessage(executionError)}
        />
      ) : null}
      {retrying ? (
        <div className="case-retry-progress" role="status" aria-live="polite">
          <div className="case-retry-progress__meta">
            <span>正在重试此 Case：{retryLabel}</span>
            <span>{retryCount}</span>
          </div>
          <Progress percent={retryPercent} status="active" strokeColor="var(--runs-purple)" />
        </div>
      ) : null}
    </DashPanel>
  );
}
