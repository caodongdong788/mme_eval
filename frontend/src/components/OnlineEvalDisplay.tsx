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
  good: "良好",
  qualified: "合格",
  unqualified: "不合格",
};

const taskTypeLabel: Record<string, string> = {
  report_interpretation: "报告解读",
  symptom_triage: "症状分诊",
  adherence_side_effect: "用药/副作用",
  general_support: "通用陪伴",
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
    score = cases.reduce((sum, item) => sum + (item.total_score || 0), 0) / cases.length;
  }
  if (!ready && score <= 0 && !cases?.length) return <>-</>;
  return (
    <span className="mono">
      {score.toFixed(1)}
      <Typography.Text type="secondary"> / 45</Typography.Text>
    </span>
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

const ROLE_GROUPS = [
  { role: "医生端", subtotal: "doctor_score", max: "doctor_max" },
  { role: "护士端", subtotal: "nurse_score", max: "nurse_max" },
  { role: "患者端", subtotal: "patient_score", max: "patient_max" },
] as const;

function dimensionsForRole(role: string) {
  return ONLINE_DIMENSIONS.filter((item) => item.role === role);
}

function scoreValue(scores: Record<string, number>, key: string) {
  const value = scores[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function roleSubtotal(
  role: string,
  scores: Record<string, number>,
  breakdown: Record<string, number>,
  subtotalKey: string,
) {
  const persisted = scoreValue(breakdown, subtotalKey);
  if (persisted > 0) return persisted;
  const raw = dimensionsForRole(role).reduce((sum, item) => sum + scoreValue(scores, item.key), 0);
  return role === "护士端" ? raw * 1.5 : raw;
}

function roleMax(role: string, breakdown: Record<string, number>, maxKey: string) {
  const persisted = scoreValue(breakdown, maxKey);
  if (persisted > 0) return persisted;
  return role === "护士端" ? 15 : dimensionsForRole(role).reduce((sum, item) => sum + item.max, 0);
}

export function DimensionBars({
  scores,
  breakdown = {},
}: {
  scores: Record<string, number>;
  breakdown?: Record<string, number>;
}) {
  const hasScores = Object.keys(scores || {}).length > 0;
  if (!hasScores) {
    return <Typography.Text type="secondary">暂无维度解析</Typography.Text>;
  }
  return (
    <div style={{ display: "grid", gap: 14 }}>
      {ROLE_GROUPS.map(({ role, subtotal, max }) => (
        <div key={role} style={{ display: "grid", gap: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <Typography.Text strong>{role}</Typography.Text>
            <Typography.Text className="mono" type="secondary">
              {roleSubtotal(role, scores, breakdown, subtotal).toFixed(1)} / {roleMax(role, breakdown, max).toFixed(1)}
              {role === "护士端" && typeof breakdown.nurse_raw_score === "number"
                ? `（原始 ${breakdown.nurse_raw_score.toFixed(1)} / ${(breakdown.nurse_raw_max || 10).toFixed(1)}）`
                : ""}
            </Typography.Text>
          </div>
          {dimensionsForRole(role).map(({ key, label, max: dimensionMax }) => {
            const value = scoreValue(scores, key);
            return (
              <div key={key}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <span>{label}</span>
                  <span className="mono">
                    {value.toFixed(1)} / {dimensionMax.toFixed(1)}
                  </span>
                </div>
                <Progress percent={Math.round((value / dimensionMax) * 100)} showInfo={false} />
              </div>
            );
          })}
        </div>
      ))}
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <Typography.Text strong>总分</Typography.Text>
        <Typography.Text className="mono">
          {(scoreValue(breakdown, "total_score") ||
            roleSubtotal("医生端", scores, breakdown, "doctor_score") +
              roleSubtotal("护士端", scores, breakdown, "nurse_score") +
              roleSubtotal("患者端", scores, breakdown, "patient_score")
          ).toFixed(1)} / {(scoreValue(breakdown, "total_max") || 45).toFixed(1)}
        </Typography.Text>
      </div>
    </div>
  );
}

export function DimensionFeedback({ row }: { row: OnlineEvalCase }) {
  if (!Object.keys(row.dimension_scores || {}).length) {
    return <Typography.Text type="secondary">暂无维度解析</Typography.Text>;
  }
  return (
    <div style={{ display: "grid", gap: 12 }}>
      {ROLE_GROUPS.map(({ role }) => (
        <div key={role} style={{ display: "grid", gap: 10 }}>
          <Typography.Text strong>{role}</Typography.Text>
          {dimensionsForRole(role).map(({ key, label, max }) => {
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
      ))}
    </div>
  );
}
