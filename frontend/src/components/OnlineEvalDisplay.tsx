import { Progress, Space, Tag, Tooltip, Typography } from "antd";
import type { OnlineEval, OnlineEvalCase, ProgressInfo } from "../api/index";
import { ONLINE_DIMENSIONS } from "../hooks/useOnlineEvalsPage";

const gateLabel: Record<string, string> = {
  pass: "通过",
  fail: "失败",
  need_human_review: "需人审",
};

const gradeLabel: Record<string, string> = {
  excellent: "优秀",
  high_quality: "可上线优质",
  acceptable: "可接受",
  risky: "风险样本",
  fail: "不合格",
};

const taskTypeLabel: Record<string, string> = {
  report_interpretation: "报告解读",
  symptom_triage: "症状分诊",
  adherence_side_effect: "用药/副作用",
  general_support: "通用陪伴",
};

const riskTagLabel: Record<string, string> = {
  assumed_context: "假设上下文",
  fact_misread: "事实读错",
  limited_personalization: "个性化不足",
  low_context_personalization: "上下文/个性化不足",
  metric_confusion: "指标混淆",
  model_requested_fail: "模型判为失败",
  multiple_questions_unanswered: "多问题未逐一回应",
  needs_more_context: "需补充上下文",
  overclaim_cure: "疗效承诺过度",
  unsafe_medication_advice: "用药建议不安全",
  video_relevance_gap: "视频相关性不足",
};

const statusLabel: Record<string, string> = {
  pending: "排队中",
  running: "评分中",
  success: "完成",
  failed: "失败",
};

export function StatusTag({ value }: { value: string }) {
  const color =
    value === "success"
      ? "success"
      : value === "failed"
        ? "error"
        : value === "running"
          ? "processing"
          : "default";
  return <Tag color={color}>{statusLabel[value] || value}</Tag>;
}

export function GateTag({ value }: { value: string }) {
  const color = value === "pass" ? "success" : value === "fail" ? "error" : "warning";
  return <Tag color={color}>{gateLabel[value] || value}</Tag>;
}

export function GradeText({ value }: { value: string }) {
  return <>{gradeLabel[value] || value}</>;
}

export function TaskTypeText({ value }: { value: string }) {
  return <>{taskTypeLabel[value] || value || "-"}</>;
}

export function AverageScoreText({
  value,
  cases,
  ready,
}: {
  value: number;
  cases?: OnlineEvalCase[];
  ready?: boolean;
}) {
  let score = Number.isFinite(value) ? value : 0;
  if (score <= 0 && cases?.length) {
    score = cases.reduce((sum, item) => sum + (item.total_score_10 || 0), 0) / cases.length;
  }
  if (!ready && score <= 0 && !cases?.length) return <>-</>;
  return <span className="mono">{score.toFixed(1)}</span>;
}

function splitRiskTag(tag: string): { raw: string; count: string } {
  const match = tag.match(/^(.*)×(\d+)$/);
  if (!match) return { raw: tag, count: "" };
  return { raw: match[1], count: `×${match[2]}` };
}

function fallbackRiskLabel(raw: string) {
  if (raw.includes("context") || raw.includes("personal")) return "上下文/个性化不足";
  if (raw.includes("question") || raw.includes("multiple")) return "多问题未逐一回应";
  if (raw.includes("relevance") || raw.includes("video")) return "相关性不足";
  if (raw.includes("unsafe") || raw.includes("medication")) return "医疗安全风险";
  return "其他风险";
}

export function RiskTags({ tags }: { tags: string[] }) {
  if (!tags.length) return <span style={{ color: "var(--muted)" }}>-</span>;
  return (
    <Space size={[4, 4]} wrap>
      {tags.map((tag) => {
        const { raw, count } = splitRiskTag(tag);
        const label = riskTagLabel[raw] || fallbackRiskLabel(raw);
        return (
          <Tooltip key={tag} title={raw}>
            <Tag>{label}{count}</Tag>
          </Tooltip>
        );
      })}
    </Space>
  );
}

export function OnlineEvalStatusCell({
  row,
  progress,
}: {
  row: OnlineEval;
  progress?: ProgressInfo;
}) {
  if (row.status === "pending" || row.status === "running") {
    const p = progress?.progress ?? row.progress;
    const title = `${p?.current_label || "等待评分"} ${p?.done || 0}/${p?.total || row.case_count || 0}`;
    return (
      <Space direction="vertical" size={2} style={{ minWidth: 140 }}>
        <StatusTag value={row.status} />
        <Tooltip title={title}>
          <Progress percent={p?.percent || 0} size="small" strokeColor="var(--runs-purple)" />
        </Tooltip>
      </Space>
    );
  }
  if (row.status === "failed") {
    return (
      <Tooltip title={row.error_msg || "评分失败"}>
        <span>
          <StatusTag value={row.status} />
        </span>
      </Tooltip>
    );
  }
  return <StatusTag value={row.status} />;
}

export function OnlineEvalProgressText({
  row,
  progress,
}: {
  row: OnlineEval;
  progress?: ProgressInfo;
}) {
  const p = progress?.progress ?? row.progress;
  return <>{p ? `${p.current_label || "-"} ${p.done || 0}/${p.total || 0}` : "-"}</>;
}

export function DimensionBars({ scores }: { scores: Record<string, number> }) {
  return (
    <div style={{ display: "grid", gap: 10 }}>
      {ONLINE_DIMENSIONS.map(({ key, label, max }) => {
        const value = scores[key] ?? 0;
        return (
          <div key={key}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span>{label}</span>
              <span className="mono">
                {value.toFixed(1)} / {max.toFixed(1)}
              </span>
            </div>
            <Progress percent={Math.round((value / max) * 100)} showInfo={false} />
          </div>
        );
      })}
    </div>
  );
}

export function DimensionFeedback({ row }: { row: OnlineEvalCase }) {
  return (
    <div style={{ display: "grid", gap: 12 }}>
      {ONLINE_DIMENSIONS.map(({ key, label, max }) => {
        const value = row.dimension_scores[key] ?? 0;
        const feedback = row.dimension_feedback?.[key] || {};
        const evidence = feedback.evidence || [];
        const suggestions = feedback.suggestions || [];
        return (
          <div key={key} style={{ borderLeft: "3px solid var(--runs-purple)", paddingLeft: 12 }}>
            <Space size={8} wrap>
              <Typography.Text strong>{label}</Typography.Text>
              <Typography.Text className="mono" type="secondary">
                {value.toFixed(1)} / {max.toFixed(1)}
              </Typography.Text>
            </Space>
            <Typography.Paragraph style={{ margin: "6px 0" }}>
              {feedback.basis || "该维度未返回单独依据，请结合完整回复复核。"}
            </Typography.Paragraph>
            <Typography.Text type="secondary">证据</Typography.Text>
            <ul style={{ marginTop: 4, marginBottom: 8 }}>
              {(evidence.length ? evidence : ["未返回单独证据"]).map((item, idx) => (
                <li key={`e-${key}-${idx}`}>{item}</li>
              ))}
            </ul>
            <Typography.Text type="secondary">建议</Typography.Text>
            <ul style={{ marginTop: 4, marginBottom: 0 }}>
              {(suggestions.length ? suggestions : ["暂无单独建议"]).map((item, idx) => (
                <li key={`s-${key}-${idx}`}>{item}</li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
