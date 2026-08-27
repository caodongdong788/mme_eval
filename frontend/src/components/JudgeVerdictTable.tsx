import { Space, Table, Tag, Typography } from "antd";
import type { GuidelineScore } from "../api";
import { useJudgeVerdictLabels } from "../hooks/useConfigLabelMap";
import { CaseVerdict } from "../utils/caseJudging";
import { DashPanel } from "./DashPanel";

const { Text } = Typography;

export interface JudgeVerdictTableProps {
  verdicts: CaseVerdict[];
  tagLabel: (tag: string) => string;
  dimensionRawScores?: Record<string, number | null>;
  dimensionScores?: Record<string, number | null>;
  dimensionMax?: Record<string, number>;
  scoreDeductions?: string[];
  guidelineScores?: GuidelineScore[];
  assertionScores?: AssertionScore[];
}

export interface AssertionScore {
  id?: string;
  standard?: string;
  dimension?: string;
  description?: string;
  passed?: boolean;
  deduction?: number;
  applied_deduction?: number;
  reason?: string;
}

function dimensionKey(name: string): string | null {
  return name.startsWith("dimension.") ? name.slice("dimension.".length) : null;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function sentence(value: string | undefined): string {
  const text = String(value || "").trim().replace(/[。；;，,]+$/, "");
  return text ? `${text}。` : "";
}

function plainRequirement(value: string | undefined): string {
  return String(value || "")
    .trim()
    .replace(/^(满分要求|评分要求)[：:]\s*/, "")
    .replace(/[。；;，,]+$/, "");
}

type DimensionAuditIssue = {
  type?: string;
  requirement?: string;
  reason?: string;
  evidence?: string[];
  evidence_refs?: Array<{
    quote?: string;
    turn_index?: number;
  }>;
};

function readableAuditIssue(issue: DimensionAuditIssue): string {
  const type = String(issue?.type || "").toLowerCase();
  const requirement = plainRequirement(issue?.requirement);
  const observed = String(issue?.reason || "").trim().replace(/[。；;，,]+$/, "");
  if (type === "missing") {
    if (/^回答(?:里)?(?:应|需|必须|务必)/.test(observed)) return sentence(observed);
    const expected = /^(应|需|必须|务必)/.test(requirement)
      ? `回答里${requirement}`
      : /^(建议|提示|说明|提醒|询问|引导|邀请|提供|列出|明确|告知|帮助)/.test(requirement)
        ? `回答里应${requirement}`
        : `回答里应满足以下要求：${requirement}`;
    const current = observed && !/^(回答|当前回答)/.test(observed) ? `当前回答${observed}` : observed;
    return sentence(current ? `${expected}；${current}` : expected);
  }
  if (type === "partial") {
    return sentence(requirement && observed ? `回答只部分满足“${requirement}”：${observed}` : observed || requirement);
  }
  if (type === "contradicted") {
    return sentence(requirement && observed ? `回答违反“${requirement}”：${observed}` : observed || requirement);
  }
  if (type === "hallucination") {
    return sentence(observed ? `回答包含无来源事实：${observed}` : requirement);
  }
  return sentence(observed || requirement);
}

function readableEvidence(issue: DimensionAuditIssue): string {
  const refs = (issue.evidence_refs || [])
    .map((ref) => ({
      quote: String(ref?.quote || "").trim(),
      turnIndex: Number(ref?.turn_index),
    }))
    .filter((ref) => ref.quote);
  if (refs.length) {
    return refs.map((ref) => (
      Number.isInteger(ref.turnIndex) && ref.turnIndex > 0
        ? `第 ${ref.turnIndex} 轮回答：${ref.quote}`
        : ref.quote
    )).join("；");
  }
  return (issue.evidence || []).join("；");
}

function StructuredDimensionReason({ verdict }: { verdict: CaseVerdict }) {
  const satisfied = (verdict.details?.satisfied_points || []).filter(Boolean);
  const issues = (verdict.details?.issue_audits || []).filter(
    (issue) => issue && (issue.reason || issue.requirement),
  );
  if (!issues.length) return <span>{verdict.reason || "—"}</span>;
  return (
    <div className="judge-audit-reason">
      {satisfied.length ? (
        <div className="judge-audit-reason__satisfied">
          <strong>已做到</strong>
          <span>{satisfied.map((item) => sentence(item)).join(" ")}</span>
        </div>
      ) : null}
      <div className="judge-audit-reason__issues">
        <strong>扣分原因</strong>
        <ol>
          {issues.map((issue, index) => (
            <li key={`${issue.requirement || "issue"}-${index}`}>
              <div>{readableAuditIssue(issue)}</div>
              {issue.evidence?.length || issue.evidence_refs?.length ? (
                <div className="judge-audit-reason__evidence">
                  <span>对应原文：</span>{readableEvidence(issue)}
                </div>
              ) : null}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

export function JudgeVerdictTable({
  verdicts,
  tagLabel,
  dimensionRawScores = {},
  dimensionScores = {},
  dimensionMax = {},
  scoreDeductions = [],
  guidelineScores = [],
  assertionScores = [],
}: JudgeVerdictTableProps) {
  const judgeLabel = useJudgeVerdictLabels();
  const dimensionVerdicts = verdicts.filter((verdict) => dimensionKey(verdict.name));
  const deductionsFor = (name: string): string[] => {
    const key = dimensionKey(name);
    if (!key) return [];
    const prefix = new RegExp(`^${escapeRegExp(key)}(?:\\s+|[：:])`);
    const structuredAssertionDeductions = assertionScores
      .filter(
        (item) =>
          item.dimension === key &&
          item.passed === false &&
          Number(item.applied_deduction || 0) > 0,
      )
      .map((item) => {
        const deduction = Number(item.applied_deduction || 0);
        const reason = item.reason || item.description || "回答未满足要求";
        return `回答要求 ${item.id || "—"} -${deduction}分：${reason}`;
      });
    const legacyDeductions = scoreDeductions
      .filter((item) => prefix.test(item))
      .map((item) => item.replace(prefix, ""))
      // 新结果优先使用 assertion_scores 的结构化数据；旧结果仍保留文案回退。
      .filter((item) => !(structuredAssertionDeductions.length && item.includes("回答要求")));
    const structuredDeductions = guidelineScores
      .filter(
        (item) =>
          item.dimension === key &&
          item.applicable !== false &&
          Number(item.deduction ?? Math.max(0, item.max_score - item.score)) > 0,
      )
      .map((item) => {
        const deduction = Number(item.deduction ?? Math.max(0, item.max_score - item.score));
        return `指南 ${item.id} -${deduction}分：${item.reason || "未完整覆盖指南要求"}`;
      });
    return Array.from(new Set([
      ...structuredDeductions,
      ...structuredAssertionDeductions,
      ...legacyDeductions,
    ]));
  };
  const columns = [
    {
      title: "维度",
      dataIndex: "name",
      width: 200,
      render: (name: string) => (
        <Space direction="vertical" size={0}>
          <Text>{judgeLabel(name)}</Text>
          <Text type="secondary" style={{ fontSize: 11 }} className="mono">
            {name}
          </Text>
        </Space>
      ),
    },
    {
      title: "结果",
      width: 80,
      render: (_: unknown, verdict: CaseVerdict) => {
        const key = dimensionKey(verdict.name);
        const finalScore = key ? (dimensionScores[key] ?? verdict.score) : verdict.score;
        const passed = key === "medical_safety"
          ? finalScore === 5
          : finalScore != null
            ? finalScore >= 3
            : verdict.passed;
        return passed ? (
          <span className="status-dot status-dot--pass">PASS</span>
        ) : (
          <span className="status-dot status-dot--fail">FAIL</span>
        );
      },
    },
    {
      title: "分数",
      width: 110,
      render: (_: unknown, v: CaseVerdict) => {
        const key = dimensionKey(v.name);
        if (!key) return v.max_score ? `${v.score}/${v.max_score}` : "-";
        const finalScore = dimensionScores[key] ?? v.score;
        const structuredDeduction = guidelineScores
          .filter((item) => item.dimension === key && item.applicable !== false)
          .reduce(
            (sum, item) =>
              sum + Number(item.deduction ?? Math.max(0, item.max_score - item.score)),
            0,
          );
        const storedRawScore = dimensionRawScores[key] ?? v.score;
        // 历史医学安全结果曾把指南门禁后的 0 分写进 raw 字段；原始维度 verdict
        // 仍保留 5 分，可据此恢复“原始 5/5 · 指南 -5分”的正确展示。
        const rawScore = structuredDeduction > 0 && Number(v.score) > Number(storedRawScore)
          ? v.score
          : storedRawScore;
        const maxScore = dimensionMax[key] ?? v.max_score;
        if (finalScore == null || maxScore == null) return "-";
        const guidelineDeduction = rawScore == null ? 0 : Math.max(0, rawScore - finalScore);
        return (
          <Space direction="vertical" size={0}>
            <span>{`最终 ${finalScore}/${maxScore}`}</span>
            {guidelineDeduction > 0 ? (
              <Text type="secondary" style={{ fontSize: 11 }}>
                {`维度原始 ${rawScore}/${maxScore} · 附加扣分 -${guidelineDeduction}分`}
              </Text>
            ) : null}
          </Space>
        );
      },
    },
    {
      title: "判定与扣分原因",
      dataIndex: "reason",
      render: (reason: string | undefined, verdict: CaseVerdict) => {
        const deductions = deductionsFor(verdict.name);
        return (
          <div className="judge-reason">
            <StructuredDimensionReason verdict={{ ...verdict, reason }} />
            {deductions.length ? (
              <div className="judge-reason__deductions">
                <strong>附加扣分</strong>
                {deductions.map((item, index) => <div key={`${item}-${index}`}>{item}</div>)}
              </div>
            ) : null}
          </div>
        );
      },
    },
    {
      title: "失败标签",
      dataIndex: "failure_tags",
      render: (t: string[]) =>
        (t || []).map((x) => (
          <Tag key={x} color="red" bordered={false}>
            {tagLabel(x)}
          </Tag>
        )),
    },
  ];

  return (
    <DashPanel title="维度评分" bodyClassName="dash-panel__body--flush">
      <Table
        className="dash-table judge-verdict-table"
        rowKey="name"
        size="small"
        columns={columns}
        dataSource={dimensionVerdicts}
        pagination={false}
      />
    </DashPanel>
  );
}
