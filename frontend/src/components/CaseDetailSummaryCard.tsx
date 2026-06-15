import { Card, Descriptions, Tag, Typography } from "antd";
import { Link } from "react-router-dom";
import { PROFILE_LABEL, STABILITY_LABEL } from "../labels";
import { CaseVerdict, guidelineMatch } from "../utils/caseJudging";

const { Text } = Typography;

export interface CaseDetailSummary {
  case?: {
    sample_id?: string;
    scenario?: string;
    sub_scenario?: string;
    level?: string;
    scoring_points?: Array<{ guideline?: string }>;
  };
  score_profile?: string;
  composite_score?: number;
  grade?: string;
  stability?: string;
  hard_gate_passed?: boolean;
  gate_passed?: boolean;
  release_passed?: boolean;
  needs_human_review?: boolean;
  trace?: { langfuse_trace_url?: string | null };
}

export interface CaseDetailSummaryCardProps {
  detail: CaseDetailSummary;
  scoringPoints: CaseVerdict[];
  backTo: string;
  backState?: unknown;
  backLabel: string;
}

export function CaseDetailSummaryCard({
  detail,
  scoringPoints,
  backTo,
  backState,
  backLabel,
}: CaseDetailSummaryCardProps) {
  const guideline = guidelineMatch(detail, scoringPoints);

  return (
    <Card
      title={
        <Link to={backTo} state={backState}>
          ← 返回{backLabel}
        </Link>
      }
    >
      <Descriptions title={`用例 ${detail.case?.sample_id}`} column={3} size="small">
        <Descriptions.Item label="场景">
          {detail.case?.sub_scenario || detail.case?.scenario}
        </Descriptions.Item>
        <Descriptions.Item label="Level">{detail.case?.level}</Descriptions.Item>
        <Descriptions.Item label="评分档">
          {PROFILE_LABEL[detail.score_profile || ""] || detail.score_profile || "-"}
        </Descriptions.Item>
        <Descriptions.Item label="综合分">
          {detail.composite_score?.toFixed?.(2) ?? "-"}
        </Descriptions.Item>
        <Descriptions.Item label="评级">{detail.grade}</Descriptions.Item>
        <Descriptions.Item label="稳定性">
          {STABILITY_LABEL[detail.stability || ""] || detail.stability || "-"}
        </Descriptions.Item>
        <Descriptions.Item label="硬门槛">
          {detail.hard_gate_passed ? "通过" : "失败"}
        </Descriptions.Item>
        <Descriptions.Item label="gate">{detail.gate_passed ? "通过" : "失败"}</Descriptions.Item>
        <Descriptions.Item label="上线判定">
          {detail.release_passed ? (
            <span className="status-dot status-dot--pass">通过</span>
          ) : (
            <span className="status-dot status-dot--fail">失败</span>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="指南匹配率">
          {!guideline ? (
            <Text type="secondary">无指南锚点</Text>
          ) : (
            `${Math.round(guideline.rate * 100)}%（${guideline.matched}/${guideline.total}）`
          )}
        </Descriptions.Item>
        {detail.trace?.langfuse_trace_url && (
          <Descriptions.Item label="追踪链路">
            <a href={detail.trace.langfuse_trace_url} target="_blank" rel="noreferrer">
              在 Langfuse 查看
            </a>
          </Descriptions.Item>
        )}
      </Descriptions>
      {detail.needs_human_review && (
        <Tag color="gold" style={{ marginTop: 8 }}>
          需人工复核
        </Tag>
      )}
    </Card>
  );
}
