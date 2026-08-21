import {
  Alert,
  Button,
  Collapse,
  Descriptions,
  Empty,
  List,
  Modal,
  Popconfirm,
  Progress,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Timeline,
  Tooltip,
  Typography,
  type CollapseProps,
  message,
} from "antd";
import {
  BulbOutlined,
  DownOutlined,
  DeleteOutlined,
  EyeOutlined,
  LinkOutlined,
  RedoOutlined,
  UpOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import {
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Link } from "react-router-dom";
import {
  api,
  type AttributionDeductionAnalysis,
  type AttributionRecommendation,
  type AttributionTask,
  type AttributionTaskItem,
  type CaseAttribution,
  type JudgeModel,
} from "../api";
import { AttributionTaskLaunchModal } from "./AttributionTaskLaunchModal";
import { formatApiError, humanizeErrorText } from "../utils/apiError";
import { EVALUATION_DIMENSIONS } from "../labels";
import {
  answerUsageDisplayName,
  attributionDeductionLabel,
  cxAgentSuggestionCategory,
  dimensionDisplayName,
  humanizeAttributionText,
  humanizeEvidenceRef,
  informationStageDisplayName,
  priorityDisplayName,
  queryQualityDisplayName,
} from "../utils/attributionDisplay";
import { formatApiDateTime } from "../utils/datetime";
import { DashPanel } from "./DashPanel";
import { usePollingTask } from "../hooks/usePollingTask";

const OWNER_LABELS: Record<string, string> = {
  benchmark: "评测判据",
  judge: "判分模型",
  agent_prompt: "提示词优化",
  orchestration: "对话流程编排",
  context_tool: "用户上下文工具",
  rag_corpus: "RAG 知识库",
  retriever: "RAG 召回",
  threshold: "RAG 阈值",
  reranker: "RAG 重排",
  generator: "回答生成",
  safety_policy: "安全策略",
  unknown: "待确认",
};
const STAGE_LABELS: Record<string, string> = {
  judge_validation: "扣分校验",
  context_fetch: "上下文读取",
  rag_decision: "RAG 调用决策",
  rag_query: "检索词生成",
  raw_recall: "原始召回",
  threshold: "阈值过滤",
  candidate: "候选生成",
  rerank: "重排选择",
  grounding: "证据利用",
  generation: "最终生成",
  patient_context_availability: "用户档案是否可用",
  context_usage: "用户信息使用情况",
  judge_verification: "判分依据复核",
  benchmark_validation: "评测判据复核",
  response_review: "回答内容核对",
  clarification: "追问策略",
};
const VALIDATION_LABELS: Record<string, { label: string; color: string }> = {
  supported: { label: "扣分成立", color: "red" },
  questionable: { label: "扣分存疑", color: "orange" },
  insufficient_evidence: { label: "证据不足", color: "default" },
};
const TASK_STATUS: Record<string, { label: string; color: string }> = {
  queued: { label: "排队中", color: "default" },
  running: { label: "分析中", color: "processing" },
  success: { label: "已完成", color: "success" },
  partial: { label: "部分完成", color: "warning" },
  failed: { label: "分析失败", color: "error" },
};

const TASK_ITEM_STATUS: Record<string, { label: string; color: string }> = {
  queued: { label: "排队中", color: "default" },
  running: { label: "分析中", color: "processing" },
  success: { label: "已完成", color: "success" },
  failed: { label: "失败", color: "error" },
};

function AttributionPanelHeading({
  title,
  subtitle,
}: {
  title: string;
  subtitle: string;
}) {
  return (
    <div className="attribution-panel-heading">
      <h3>{title}</h3>
      <span className="dash-table-card__sub">{subtitle}</span>
    </div>
  );
}

function AttributionStatusTag({
  status,
  task = false,
  runtimeStatus,
  retryCount = 0,
}: {
  status: string;
  task?: boolean;
  runtimeStatus?: string;
  retryCount?: number;
}) {
  if (!task && status === "running" && runtimeStatus) {
    const runtimeMeta =
      runtimeStatus === "preparing_evidence"
        ? { label: "整理证据", color: "processing" }
        : runtimeStatus === "retrying"
          ? { label: `重试第${retryCount || 1}次`, color: "warning" }
          : { label: "模型调用中", color: "processing" };
    return (
      <Tag className="attribution-status-tag" color={runtimeMeta.color}>
        {runtimeMeta.label}
      </Tag>
    );
  }
  const meta =
    (task ? TASK_STATUS : TASK_ITEM_STATUS)[status] ||
    (task ? TASK_STATUS.failed : TASK_ITEM_STATUS.failed);
  return (
    <Tag className="attribution-status-tag" color={meta.color}>
      {meta.label}
    </Tag>
  );
}

function AttributionItemProgress({ item }: { item: AttributionTaskItem }) {
  const manuallyRetried = (item.attempt_count || 0) > 0;
  const runtimeLabel = item.runtime_message?.trim();
  const meta =
    item.status === "pending"
      ? { percent: 0, status: "normal" as const, label: runtimeLabel || (manuallyRetried ? "等待重试" : "排队中") }
      : item.status === "running"
        ? {
            percent: item.runtime_status === "preparing_evidence" ? 25 : item.runtime_status === "retrying" ? 70 : 55,
            status: "active" as const,
            label: runtimeLabel || (manuallyRetried ? "重试中" : "分析中"),
          }
        : item.status === "success"
          ? { percent: 100, status: "success" as const, label: runtimeLabel || (manuallyRetried ? "重试完成" : "已完成") }
          : { percent: 100, status: "exception" as const, label: runtimeLabel || (manuallyRetried ? "重试失败" : "失败") };
  return (
    <div className="attribution-item-progress">
      <Progress
        percent={meta.percent}
        status={meta.status}
        showInfo={false}
        size="small"
      />
      <span>{meta.label}</span>
    </div>
  );
}

function AttributionTaskProgress({ task }: { task: AttributionTask }) {
  const runningCount = task.running_count || 0;
  const pendingCount = Number.isFinite(task.pending_count)
    ? task.pending_count
    : Math.max(0, task.total_count - task.completed_count - runningCount);
  // 汇总进度只表示已落库的终态 Case（成功或失败）。运行中的 Case 已进入
  // 并发槽位但尚未产出结果，不能提前计入完成率，否则“20/22 + 分析中 2”会
  // 错误显示为 100%。
  const terminalCount = Math.min(task.total_count, task.completed_count);
  const percent = task.total_count
    ? Math.round((terminalCount / task.total_count) * 100)
    : 0;
  const progressStatus =
    task.status === "failed"
      ? "exception"
      : task.status === "success"
        ? "success"
        : "active";
  const progressColor =
    task.status === "partial"
      ? "var(--warn)"
      : task.status === "success"
        ? "var(--pass)"
        : task.status === "failed"
          ? "var(--fail)"
          : "var(--runs-purple)";

  return (
    <div className="attribution-task-progress">
      <Progress
        percent={percent}
        size="small"
        status={progressStatus}
        strokeColor={progressColor}
      />
      <div className="attribution-muted">
        已完成 {task.completed_count}/{task.total_count}
        {runningCount ? ` · 分析中 ${runningCount}` : ""}
        {pendingCount ? ` · 等待 ${pendingCount}` : ""}
        {task.failed_count ? ` · 失败 ${task.failed_count}` : ""}
      </div>
    </div>
  );
}

function AttributionActionButton({
  children,
  danger,
  disabled,
  icon,
  loading,
  onClick,
}: {
  children: ReactNode;
  danger?: boolean;
  disabled?: boolean;
  icon?: ReactNode;
  loading?: boolean;
  onClick?: () => void;
}) {
  return (
    <Button
      className="attribution-action-button"
      danger={danger}
      disabled={disabled}
      icon={icon}
      loading={loading}
      onClick={onClick}
      size="small"
      type="link"
    >
      {children}
    </Button>
  );
}

function normalizeTaskCounts(task: AttributionTask): AttributionTask {
  const runningCount = Number.isFinite(task.running_count)
    ? task.running_count
    : task.items.filter((item) => item.status === "running").length;
  const pendingCount = Number.isFinite(task.pending_count)
    ? task.pending_count
    : Math.max(0, task.total_count - task.completed_count - runningCount);
  return { ...task, running_count: runningCount, pending_count: pendingCount };
}

function confidencePercent(value?: number) {
  return Math.round(Math.max(0, Math.min(1, Number(value || 0))) * 100);
}

const RECOMMENDATION_DIRECTIONS = [
  {
    key: "prompt",
    label: "提示词优化",
    pattern: /提示词|prompt|agent_prompt/i,
  },
  {
    key: "rag",
    label: "RAG 优化",
    pattern: /\brag\b|知识库|文献|检索|召回|重排|阈值/i,
  },
  {
    key: "flow",
    label: "对话流程优化",
    pattern: /对话流程|流程编排|追问|orchestration/i,
  },
  {
    key: "response",
    label: "回答策略优化",
    pattern: /回答策略|回答生成|生成模型|表达|\bagent\b|AI\s*助手/i,
  },
  {
    key: "context",
    label: "上下文使用优化",
    pattern: /用户档案|用户上下文|上下文工具|context/i,
  },
  {
    key: "safety",
    label: "安全策略优化",
    pattern: /安全策略|安全门禁|safety/i,
  },
  {
    key: "benchmark",
    label: "评测判据优化",
    pattern: /benchmark|评测判据|评分标准|判据/i,
  },
  {
    key: "judge_prompt",
    label: "判分提示词优化",
    pattern: /判分提示词|评测提示词|judge[ _-]?prompt/i,
  },
  {
    key: "judge_context",
    label: "判分上下文优化",
    pattern: /判分上下文|评测上下文/i,
  },
  {
    key: "judge_evidence",
    label: "判分证据核验",
    pattern: /判分证据|证据核验/i,
  },
  {
    key: "judge_consistency",
    label: "判分一致性优化",
    pattern: /判分一致性|评分一致性/i,
  },
  {
    key: "judge",
    label: "判分模型优化",
    pattern: /judge|判分模型|判分逻辑|评测模型/i,
  },
  {
    key: "evidence",
    label: "证据采集优化",
    pattern: /证据采集|调用链|链路|审计|可观测|trace|observability/i,
  },
] as const;

function recommendationDirection(item: AttributionRecommendation) {
  const target = item.target || "";
  const action = item.action || "";
  const judgeTarget =
    /judge|判分模型|判分逻辑|评测模型|判分提示词|评测提示词/i.test(target);
  if (judgeTarget) {
    if (/判分提示词|评测提示词|judge[ _-]?prompt/i.test(target))
      return RECOMMENDATION_DIRECTIONS.find(
        (item) => item.key === "judge_prompt"
      );
    if (/注入|可见上下文|上下文输入/i.test(action))
      return RECOMMENDATION_DIRECTIONS.find(
        (item) => item.key === "judge_context"
      );
    if (/全文检索|关键词|证据|核对|引用|命中|原文/i.test(action))
      return RECOMMENDATION_DIRECTIONS.find(
        (item) => item.key === "judge_evidence"
      );
    if (/逐条对齐|一致性|自相矛盾|判据鼓励|评分标准/i.test(action))
      return RECOMMENDATION_DIRECTIONS.find(
        (item) => item.key === "judge_consistency"
      );
    if (/提示词|指令|规则|必须|强制|不得/i.test(action))
      return RECOMMENDATION_DIRECTIONS.find(
        (item) => item.key === "judge_prompt"
      );
    return RECOMMENDATION_DIRECTIONS.find((item) => item.key === "judge");
  }
  return (
    RECOMMENDATION_DIRECTIONS.find((candidate) =>
      candidate.pattern.test(target)
    ) ||
    RECOMMENDATION_DIRECTIONS.find((candidate) =>
      candidate.pattern.test(action)
    )
  );
}

function groupedRecommendations(items: AttributionRecommendation[]) {
  const groups = new Map<
    string,
    { key: string; label: string; items: AttributionRecommendation[] }
  >();
  items.forEach((item) => {
    const direction = recommendationDirection(item);
    const key = direction?.key || "other";
    const group = groups.get(key) || {
      key,
      label: direction?.label || "其他优化",
      items: [],
    };
    group.items.push(item);
    groups.set(key, group);
  });
  return [...groups.values()].sort((left, right) => {
    const leftIndex = RECOMMENDATION_DIRECTIONS.findIndex(
      (item) => item.key === left.key
    );
    const rightIndex = RECOMMENDATION_DIRECTIONS.findIndex(
      (item) => item.key === right.key
    );
    return (
      (leftIndex < 0 ? Number.MAX_SAFE_INTEGER : leftIndex) -
      (rightIndex < 0 ? Number.MAX_SAFE_INTEGER : rightIndex)
    );
  });
}

function RecommendationList({ items }: { items: AttributionRecommendation[] }) {
  if (!items?.length)
    return (
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无优化建议" />
    );
  return (
    <div className="attribution-recommendation-groups">
      {groupedRecommendations(items).map((group) => (
        <section className="attribution-recommendation-group" key={group.key}>
          <div className="attribution-recommendation-group__title">
            <strong>{group.label}</strong>
            <Tag>{group.items.length} 项</Tag>
          </div>
          <List
            className="attribution-recommendations"
            dataSource={group.items}
            renderItem={(item) => (
              <List.Item>
                <div>
                  <Tag
                    color={
                      item.priority === "P0"
                        ? "red"
                        : item.priority === "P1"
                          ? "orange"
                          : "blue"
                    }
                  >
                    {priorityDisplayName(item.priority)}
                  </Tag>
                  <div className="attribution-recommendations__action">
                    <strong>怎么优化：</strong>
                    {humanizeAttributionText(item.action)}
                  </div>
                </div>
              </List.Item>
            )}
          />
        </section>
      ))}
    </div>
  );
}

type AttributionModuleKind = "supported" | "questionable" | "insufficient";

const QUESTIONABLE_REVIEW_GROUPS = [
  {
    key: "benchmark_criteria_conflict",
    title: "Benchmark 判据冲突",
    description:
      "检查点、扣分规则、推荐回答或适用条件彼此矛盾，需先修正 Benchmark 的评测真值。",
  },
  {
    key: "annotation_rag_conflict",
    title: "标注与 RAG 证据冲突",
    description:
      "已有标注或判分结论与本用例可核对的 RAG 医学证据不一致，需复核证据与真值。",
  },
  {
    key: "judge_logic_issue",
    title: "其他判分复核",
    description:
      "判据本身暂未发现冲突，但判分可能漏读上下文、条件限制或扣分档位，需复核判分逻辑。",
  },
] as const;

function questionableReviewGroup(
  item: AttributionDeductionAnalysis
): (typeof QUESTIONABLE_REVIEW_GROUPS)[number]["key"] {
  if (item.evaluation_issue_category === "benchmark_criteria_conflict") {
    return "benchmark_criteria_conflict";
  }
  if (item.evaluation_issue_category === "annotation_rag_conflict") {
    return "annotation_rag_conflict";
  }
  return "judge_logic_issue";
}

const REQUIRED_INFORMATION_LABELS: Record<string, string> = {
  patient_context: "用户档案与历史事实",
  literature: "医学文献与指南",
  reasoning: "回答判断依据",
  clarification: "追问过程",
  safety_policy: "安全策略执行记录",
};

function AttributionEvidenceContent({
  item,
  analyses,
}: {
  item: AttributionDeductionAnalysis;
  analyses: AttributionDeductionAnalysis[];
}) {
  const summary = String(item.evidence_summary || "").trim();
  const excerpts = [...new Set(
    (item.observed_gap?.direct_evidence || [])
      .map((value) => String(value || "").trim())
      .filter((value) => value && value !== summary)
  )];
  const refs = [...new Set([
    ...(item.primary_cause?.evidence_refs || []),
    ...(item.contributing_causes || []).flatMap((cause) => cause.evidence_refs || []),
    ...(item.causal_chain || []).flatMap((step) => step.evidence_refs || []),
  ])];
  const readableRefs = [...new Set(
    refs.map((ref) => humanizeEvidenceRef(ref, analyses)).filter(Boolean)
  )];
  if (!summary && !excerpts.length && !refs.length) {
    return <>暂无可引用的直接证据</>;
  }
  return (
    <Space direction="vertical" size={4}>
      {summary ? <span>{humanizeAttributionText(summary, analyses)}</span> : null}
      {excerpts.map((excerpt) => (
        <Typography.Text key={excerpt} type="secondary">
          原文：{humanizeAttributionText(excerpt, analyses)}
        </Typography.Text>
      ))}
      {readableRefs.length ? (
        <Space size={4} wrap>
          <Typography.Text type="secondary">证据范围：</Typography.Text>
          {readableRefs.map((ref) => (
            <Tag key={ref}>{ref}</Tag>
          ))}
        </Space>
      ) : null}
    </Space>
  );
}

function DeductionPanel({
  item,
  analyses,
  kind,
}: {
  item: AttributionDeductionAnalysis;
  analyses: AttributionDeductionAnalysis[];
  kind: AttributionModuleKind;
}) {
  const validation =
    item.evaluation_issue_category === "missing_rag_reference"
      ? { label: "缺少 RAG 引用", color: "blue" }
      : VALIDATION_LABELS[item.deduction_validation] ||
        VALIDATION_LABELS.insufficient_evidence;
  const cause = item.primary_cause || {
    label: "待确认",
    owner: "unknown",
    confidence: 0,
  };
  const findingTitle =
    kind === "supported"
      ? "确认的问题"
      : kind === "questionable"
        ? "为什么需要复核"
        : "目前能得出的结论";
  const chainTitle =
    kind === "supported"
      ? "问题是怎么产生的"
      : kind === "questionable"
        ? "判分复核依据"
        : "现有证据检查";
  return (
    <div className="attribution-deduction">
      <div className="attribution-gap-card">
        <div className="attribution-section-title">评测要求与实际差距</div>
        <Descriptions size="small" column={1} bordered>
          <Descriptions.Item label="期望行为">
            {humanizeAttributionText(
              item.observed_gap?.expected ||
                item.rubric_contract?.expected_behavior?.join("；"),
              analyses
            )}
          </Descriptions.Item>
          <Descriptions.Item label="实际表现">
            {humanizeAttributionText(item.observed_gap?.actual, analyses)}
          </Descriptions.Item>
          <Descriptions.Item label="明确差距">
            {humanizeAttributionText(
              item.observed_gap?.gap || item.finding,
              analyses
            )}
          </Descriptions.Item>
          <Descriptions.Item label="直接证据">
            <AttributionEvidenceContent item={item} analyses={analyses} />
          </Descriptions.Item>
          <Descriptions.Item label="导致问题">
            {humanizeAttributionText(
              item.impact || item.observed_gap?.gap || item.finding,
              analyses
            )}
          </Descriptions.Item>
        </Descriptions>
      </div>
      <div className="attribution-deduction__summary">
        <div className="attribution-section-title">{findingTitle}</div>
        <Space size={8} wrap>
          <Tag color={validation.color}>{validation.label}</Tag>
          <Tag color="purple">
            {humanizeAttributionText(cause.label || "原因待确认", analyses)}
          </Tag>
          <Tag>
            {kind === "insufficient"
              ? "暂不归责"
              : `责任环节：${OWNER_LABELS[cause.owner] || "待确认"}`}
          </Tag>
        </Space>
        <div className="attribution-deduction__finding">
          {humanizeAttributionText(
            item.finding || cause.reason || "暂无结论",
            analyses
          )}
        </div>
        <div className="attribution-confidence">
          <span>归因置信度</span>
          <Progress
            percent={confidencePercent(cause.confidence)}
            size="small"
            strokeColor="var(--runs-purple)"
          />
        </div>
      </div>
      <div className="attribution-section-title">{chainTitle}</div>
      {item.causal_chain?.length ? (
        <Timeline
          items={item.causal_chain.map((step) => ({
            color:
              step.status === "fail"
                ? "red"
                : step.status === "pass"
                  ? "green"
                  : "gray",
            children: (
              <div>
                <strong>{STAGE_LABELS[step.stage] || "其他分析环节"}</strong>
                <div>{humanizeAttributionText(step.finding, analyses)}</div>
                {step.evidence_refs?.length ? (
                  <div className="attribution-evidence">
                    证据范围：
                    {[...new Set(step.evidence_refs
                      .map((ref) => humanizeEvidenceRef(ref, analyses)))]
                      .join("、")}
                  </div>
                ) : null}
              </div>
            ),
          }))}
        />
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无完整因果链"
        />
      )}
      {kind === "supported" && item.root_cause_test?.if_fixed ? (
        <Alert
          type={
            item.root_cause_test.would_prevent_issue ? "success" : "warning"
          }
          showIcon
          message="根因反事实检查"
          description={
            <div>
              <strong>如果修复：</strong>
              {humanizeAttributionText(item.root_cause_test.if_fixed, analyses)}
              <br />
              <strong>判断：</strong>
              {humanizeAttributionText(item.root_cause_test.reason, analyses)}
            </div>
          }
        />
      ) : null}
      <div className="attribution-section-title">医学知识检索对本项的影响</div>
      <Descriptions size="small" column={{ xs: 1, md: 2, lg: 4 }}>
        <Descriptions.Item label="是否需要">
          {item.rag_diagnosis?.needed ? "需要" : "不需要"}
        </Descriptions.Item>
        <Descriptions.Item label="实际调用">
          {item.rag_diagnosis?.called ? "已调用" : "未调用"}
        </Descriptions.Item>
        <Descriptions.Item label="查询质量">
          {queryQualityDisplayName(item.rag_diagnosis?.query_quality)}
        </Descriptions.Item>
        <Descriptions.Item label="相关信息到达阶段">
          {informationStageDisplayName(
            item.rag_diagnosis?.relevant_information_stage
          )}
        </Descriptions.Item>
        <Descriptions.Item label="回答利用情况" span={2}>
          {answerUsageDisplayName(item.rag_diagnosis?.answer_usage)}
        </Descriptions.Item>
        <Descriptions.Item label="结论" span={2}>
          {humanizeAttributionText(item.rag_diagnosis?.finding, analyses)}
        </Descriptions.Item>
      </Descriptions>
    </div>
  );
}

function isEvaluationRecommendation(item: AttributionRecommendation) {
  if (item.scope) return item.scope === "evaluation";
  return /benchmark|judge|评测|判分|判据|评分/i.test(
    `${item.target} ${item.action}`
  );
}

function isEvidenceRecommendation(item: AttributionRecommendation) {
  if (item.scope) return item.scope === "evidence";
  return (
    !isEvaluationRecommendation(item) &&
    /证据采集|链路|审计|可观测|trace|observability|candidate_membership|上下文采集/i.test(
      item.target
    )
  );
}

function uniqueRecommendations(items: AttributionRecommendation[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = `${item.target}::${item.action}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function fallbackRecommendation(
  kind: AttributionModuleKind,
  item: AttributionDeductionAnalysis
): AttributionRecommendation {
  const label = attributionDeductionLabel(item);
  if (item.evaluation_issue_category === "missing_rag_reference") {
    return {
      priority: "P1",
      target: "RAG 引用",
      action: `为“${label}”涉及的医学事实建立回答片段与检索原文的可回链引用；无法提供来源时避免将结论表述为确定事实。`,
      expected_effect: "让回答中的医学结论可追溯，并能明确区分知识依据、RAG 召回和 Benchmark 判据。",
      verification: `使用当前用例重新回归，确认“${label}”中的关键医学结论可定位到对应 RAG 原文。`,
      acceptance_criteria: "每条需要医学依据的结论均能展示有效的 RAG 来源或明确说明未引用依据。",
    };
  }
  if (kind === "supported") {
    return {
      priority: "P1",
      target: "AI 助手回答策略",
      action: `在提示词或对话流程中增加“${label}”输出前检查，避免再次出现：${humanizeAttributionText(item.finding)}`,
      expected_effect: "减少同类真实问题再次发生",
      verification: `使用当前用例及同类边界用例回归，确认“${label}”不再被扣分。`,
    };
  }
  if (kind === "questionable") {
    return {
      priority: "P0",
      target: "评测判据与判分模型",
      action: `对照对话原文、用户档案和医学证据，重新核对“${label}”的适用条件、扣分档位和证据引用；判据与权威证据冲突时修订判据，判分模型漏读时修订判分提示词。`,
      expected_effect: "避免正确回答被误扣，或因证据读取不全产生错误判分",
      verification: `使用当前用例和同类边界用例重新判分，确认“${label}”结论与引用证据一致。`,
    };
  }
  const required =
    (item.required_information || [])
      .map((key) => REQUIRED_INFORMATION_LABELS[key] || key)
      .join("、") || "完整调用链和判分依据";
  return {
    priority: "P1",
    target: "归因证据采集",
    action: `补齐“${label}”需要的${required}，证据齐全前不要将问题归责给 AI 助手或评测系统。`,
    expected_effect: "让后续归因可以形成可验证结论",
    verification:
      "补齐证据后重新归因，确认该项能进入“问题成立”或“判分需复核”。",
  };
}

function moduleRecommendations(
  kind: AttributionModuleKind,
  items: AttributionDeductionAnalysis[],
  globalItems: AttributionRecommendation[]
) {
  const own = items.flatMap((item) => item.recommendations || []);
  const combined = [...own, ...globalItems];
  const matched = combined.filter((item) => {
    if (kind === "supported")
      return (
        !isEvaluationRecommendation(item) && !isEvidenceRecommendation(item)
      );
    if (kind === "questionable") return isEvaluationRecommendation(item);
    return isEvidenceRecommendation(item);
  });
  return uniqueRecommendations(
    matched.length
      ? matched
      : items.map((item) => fallbackRecommendation(kind, item))
  );
}

const PRIORITY_ORDER = ["P0", "P1", "P2"] as const;

function priorityForDeduction(item: AttributionDeductionAnalysis) {
  const recommendationPriorities = (item.recommendations || [])
    .map((recommendation) => String(recommendation.priority || "").toUpperCase())
    .filter((priority) => PRIORITY_ORDER.includes(priority as (typeof PRIORITY_ORDER)[number]));
  if (recommendationPriorities.length) {
    return recommendationPriorities.sort(
      (left, right) =>
        PRIORITY_ORDER.indexOf(left as (typeof PRIORITY_ORDER)[number]) -
        PRIORITY_ORDER.indexOf(right as (typeof PRIORITY_ORDER)[number])
    )[0];
  }
  if (item.severity === "critical") return "P0";
  if (item.severity === "high") return "P1";
  return "P2";
}

function cxAgentDeductionOptimizationActions(
  item: AttributionDeductionAnalysis,
  categoryKey: string
) {
  const actions = [...new Set(
    (item.recommendations || [])
      .map((recommendation) => String(recommendation.action || "").trim())
      .filter(Boolean)
  )];
  return actions.length
    ? actions
    : [fallbackCxAgentOptimizationAction(categoryKey)];
}

function CxAgentDeductionPriorityGroups({
  items,
}: {
  items: AttributionDeductionAnalysis[];
}) {
  return (
    <div className="attribution-suggestion-groups">
      {PRIORITY_ORDER.map((priority) => {
        const priorityItems = items.filter(
          (item) => priorityForDeduction(item) === priority
        );
        if (!priorityItems.length) return null;
        return (
          <div className="attribution-priority-group" key={priority}>
            <div className="attribution-priority-group__head">
              <Tag color={priority === "P0" ? "red" : priority === "P1" ? "orange" : "blue"}>
                {priority} · {priorityDisplayName(priority)}
              </Tag>
              <span>{priorityItems.length} 个问题</span>
            </div>
            <Collapse
              className="attribution-cluster-list attribution-cluster-list--nested"
              items={priorityItems.map((item) => {
                const category = cxAgentSuggestionCategory({
                  owner: item.primary_cause?.owner,
                  evaluation_issue_category: item.evaluation_issue_category,
                  cause_code: item.primary_cause?.code,
                  rag_diagnosis: item.rag_diagnosis,
                  optimization_classification: item.optimization_classification,
                  recommendations: item.recommendations,
                });
                const actions = cxAgentDeductionOptimizationActions(item, category.key);
                return {
                  key: item.deduction_id,
                  label: (
                    <div className="attribution-cluster-label">
                      <strong>问题分类：{category.label}</strong>
                    </div>
                  ),
                  children: (
                    <div className="attribution-cluster-detail attribution-cluster-detail--optimization">
                      <div className="attribution-optimization-field">
                        <strong>问题描述：</strong>
                        {humanizeAttributionText(item.finding || item.primary_cause?.label)}
                      </div>
                      <div className="attribution-optimization-field">
                        <strong>直接证据：</strong>
                        <AttributionEvidenceContent item={item} analyses={items} />
                      </div>
                      <div className="attribution-optimization-field">
                        <strong>导致问题：</strong>
                        {humanizeAttributionText(
                          item.impact || item.observed_gap?.gap || item.finding
                        )}
                      </div>
                      <div className="attribution-optimization-field">
                        <strong>怎么优化：</strong>
                        <ol className="attribution-optimization-actions">
                          {actions.map((action) => (
                            <li key={action}>{humanizeAttributionText(action)}</li>
                          ))}
                        </ol>
                      </div>
                    </div>
                  ),
                };
              })}
            />
          </div>
        );
      })}
    </div>
  );
}

function AttributionAnalysisModule({
  kind,
  title,
  description,
  items,
  allItems,
  globalRecommendations,
}: {
  kind: AttributionModuleKind;
  title: string;
  description: string;
  items: AttributionDeductionAnalysis[];
  allItems: AttributionDeductionAnalysis[];
  globalRecommendations: AttributionRecommendation[];
}) {
  const color =
    kind === "supported"
      ? "red"
      : kind === "questionable"
        ? "orange"
        : "default";
  const adviceTitle =
    kind === "supported"
      ? "优化建议"
      : kind === "questionable"
        ? "可执行优化操作"
        : "需要补充的证据";
  const adviceDescription =
    kind === "supported"
      ? "以下建议只针对已确认的 AI 助手、RAG 或对话流程问题。"
      : kind === "questionable"
        ? "以下建议只针对 Benchmark 判据、判分模型和评测证据读取问题。"
        : "补齐缺失的调用链、用户上下文或 RAG 审计后，再判断责任归属，避免误改 AI 助手或评测规则。";
  const recommendations = moduleRecommendations(
    kind,
    items,
    globalRecommendations
  );
  const [expanded, setExpanded] = useState(false);
  const reviewGroups = QUESTIONABLE_REVIEW_GROUPS.map((group) => ({
    ...group,
    items: items.filter(
      (item) => questionableReviewGroup(item) === group.key
    ),
  })).filter((group) => group.items.length > 0);
  const deductionItems = (values: AttributionDeductionAnalysis[]) =>
    values.map((item, index) => ({
      key: item.deduction_id,
      label: (
        <div className="attribution-module__item-label">
          <strong>
            {index + 1}. {attributionDeductionLabel(item)}
          </strong>
          <span>
            {humanizeAttributionText(
              item.finding || item.primary_cause?.label,
              allItems
            )}
          </span>
        </div>
      ),
      children: <DeductionPanel item={item} analyses={allItems} kind={kind} />,
    }));
  const supportedDimensionItems: NonNullable<CollapseProps["items"]> =
    EVALUATION_DIMENSIONS.flatMap((dimension, index) => {
      const dimensionItems = items.filter((item) => item.dimension === dimension);
      if (!dimensionItems.length) return [];
      return [{
        key: dimension,
        label: (
          <div className="attribution-dimension-heading">
            <span className="attribution-dimension-index">
              {String(index + 1).padStart(2, "0")}
            </span>
            <strong>{dimensionDisplayName(dimension)}</strong>
            <span className="attribution-dimension-count">
            {dimensionItems.length} 项优化点
          </span>
        </div>
      ),
        children: <CxAgentDeductionPriorityGroups items={dimensionItems} />,
      }];
    });
  const unassignedSupportedItems = items.filter(
    (item) => !EVALUATION_DIMENSIONS.includes(item.dimension as never)
  );
  if (unassignedSupportedItems.length) {
    supportedDimensionItems.push({
      key: "unassigned",
      label: (
        <div className="attribution-dimension-heading">
          <span className="attribution-dimension-index">—</span>
          <strong>尚未关联维度</strong>
          <span className="attribution-dimension-count">
            {unassignedSupportedItems.length} 项优化点
          </span>
        </div>
      ),
      children: (
        <CxAgentDeductionPriorityGroups items={unassignedSupportedItems} />
      ),
    });
  }
  // 空分类不占页面空间；全局说明不是待补充证据条目，不能单独展示一个“0 项”模块。
  if (!items.length) return null;
  return (
    <section className={`attribution-module attribution-module--${kind}`}>
      <div className="attribution-module__header">
        <div>
          <Space size={8}>
            <h3>{title}</h3>
            <Tag color={color}>{items.length} 项</Tag>
          </Space>
          <p>{description}</p>
        </div>
        <Button
          type="link"
          size="small"
          aria-label={`${title}${expanded ? "收起" : "展开"}`}
          icon={expanded ? <UpOutlined /> : <DownOutlined />}
          onClick={() => setExpanded((current) => !current)}
        >
          {expanded ? "收起列表" : "展开列表"}
        </Button>
      </div>
      {expanded && kind === "supported" ? (
        <Collapse
          className="attribution-dimension-list"
          items={supportedDimensionItems}
        />
      ) : expanded && kind === "questionable" && items.length ? (
        <div className="attribution-review-groups">
          {reviewGroups.map((group) => (
            <section className="attribution-review-group" key={group.key}>
              <div className="attribution-review-group__head">
                <div>
                  <strong>{group.title}</strong>
                  <p>{group.description}</p>
                </div>
                <Tag color="orange">{group.items.length} 项</Tag>
              </div>
              {group.items.length ? (
                <Collapse
                  className="attribution-collapse attribution-module__items"
                  items={deductionItems(group.items)}
                />
              ) : (
                <div className="attribution-review-group__empty">本用例暂无此类复核项</div>
              )}
            </section>
          ))}
        </div>
      ) : expanded && items.length ? (
        <Collapse
          className="attribution-collapse attribution-module__items"
          items={deductionItems(items)}
        />
      ) : expanded ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={`暂无${title}`}
        />
      ) : null}
      {expanded && kind !== "supported" && recommendations.length ? (
        <div className="attribution-module__advice">
          <div className="attribution-module__advice-title">
            <BulbOutlined />
            <div>
              <strong>{adviceTitle}</strong>
              <span>{adviceDescription}</span>
            </div>
          </div>
          {recommendations.length ? (
            <RecommendationList items={recommendations} />
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export function AttributionDetail({ result }: { result: CaseAttribution }) {
  const analysis = result.analysis;
  if (!analysis) return null;
  const deductions = [...(analysis.deduction_analyses || [])].sort(
    (left, right) => {
      const leftSafety = left.dimension === "medical_safety" ? 0 : 1;
      const rightSafety = right.dimension === "medical_safety" ? 0 : 1;
      if (leftSafety !== rightSafety) return leftSafety - rightSafety;
      return left.deduction_id.localeCompare(right.deduction_id);
    }
  );
  const ragReferenceMissing = deductions.filter(
    (item) => item.evaluation_issue_category === "missing_rag_reference"
  );
  const supported = deductions.filter(
    (item) =>
      item.deduction_validation === "supported" &&
      item.evaluation_issue_category !== "missing_rag_reference"
  );
  const evaluationToolIssues = deductions.filter(
    (item) => item.deduction_validation === "questionable"
  );
  const insufficient = deductions.filter(
    (item) =>
      item.deduction_validation === "insufficient_evidence" &&
      item.evaluation_issue_category !== "missing_rag_reference"
  );
  return (
    <div className="attribution-layout">
      {result.stale ? (
        <Alert
          type="warning"
          showIcon
          message="用例证据已变化，当前结果可能过期"
          description="请从用例明细重新发起归因任务。"
        />
      ) : null}
      <AttributionAnalysisModule
        kind="supported"
        title="cx-agent 优化建议"
        description="仅展示存在优化点的维度；每个维度内按 P0/P1/P2 和文档中的一级/二级问题分类展示。"
        items={[...supported, ...ragReferenceMissing]}
        allItems={deductions}
        globalRecommendations={analysis.global_recommendations || []}
      />
      <AttributionAnalysisModule
        kind="questionable"
        title="评测工具优化建议"
        description="展示本用例中 Benchmark 判据、标注与 RAG 证据、判分模型或判分上下文的问题，并给出对应的优化操作。"
        items={evaluationToolIssues}
        allItems={deductions}
        globalRecommendations={analysis.global_recommendations || []}
      />
      {insufficient.length ? (
        <AttributionAnalysisModule
          kind="insufficient"
          title="待补充证据"
          description="仅在当前证据无法确认责任时展示，说明缺少的调用链、用户上下文或 RAG 阶段证据，以及需要补充的采集内容。"
          items={insufficient}
          allItems={deductions}
          globalRecommendations={analysis.global_recommendations || []}
        />
      ) : null}
      <div className="attribution-meta">
        分析模型：{result.metadata.model || "—"} · 分析时间：
        {formatApiDateTime(result.metadata.generated_at)}
      </div>
    </div>
  );
}

function CaseAttributionLinks({
  task,
  sampleIds,
}: {
  task: AttributionTask;
  sampleIds: string[];
}) {
  const ids = [...new Set(sampleIds)].sort((left, right) =>
    left.localeCompare(right, undefined, { numeric: true })
  );
  return (
    <Space size={[4, 4]} wrap>
      {ids.map((sampleId) => (
        <Link
          key={sampleId}
          aria-label={`查看 ${sampleId} 归因`}
          to={`/runs/${task.run_id}/attribution-tasks/${task.id}/cases/${encodeURIComponent(sampleId)}`}
        >
          {sampleId}
        </Link>
      ))}
    </Space>
  );
}

type AttributionCluster = NonNullable<
  AttributionTask["diagnostic_summary"]
>["clusters"][number];

function fallbackCxAgentOptimizationAction(categoryKey: string) {
  const actions: Record<string, string> = {
    "rag:未触发检索": "补齐 RAG 触发条件：当问题涉及医学事实、药物或个体化风险时，先检索再生成回答。",
    "rag:调用失败": "修复 RAG 调用、超时、重试与降级链路，并将调用失败与未触发检索区分记录。",
    "rag:排序或重排不当": "调整候选重排，使最符合当前患者条件与问题约束的证据优先进入上下文。",
    "rag:已召回但未使用": "增加回答前证据覆盖检查，要求关键医学结论实际使用已召回的证据。",
    "rag:证据误读": "要求先核对文献的适用人群、前提条件和结论边界，再进行医学解释。",
    "rag:缺少 RAG 引用": "为关键医学结论补齐可回链的 RAG 原文引用，并在回答中明确绑定引用。",
    "engineering:工具未调用": "明确必调工具的触发条件，确保模型能发现并调用对应工具。",
    "engineering:工具选择错误": "补充工具选择规则与失败后的替代路径，避免选错或跳过必要工具。",
    "engineering:工具参数错误": "收紧工具参数 Schema，并补齐必填项、枚举值与上下文映射。",
    "engineering:工具执行失败": "修复工具或模型执行的超时、重试、错误回传和降级链路。",
    "engineering:Timeline 或用户事实未注入": "把必要的用户档案、病历、Timeline 和历史对话注入当前回合的可见上下文。",
    "engineering:上下文已注入但未使用": "在生成前增加上下文消费约束，要求关键结论显式使用已注入的用户事实。",
    "engineering:多轮状态丢失": "修复会话状态持久化与回合间传递，避免关键事实在多轮对话中丢失。",
    "engineering:流程路由错误": "校正意图识别、流程分流与能力开关，让用例进入正确的处理链路。",
    "engineering:模型超时": "统一模型调用超时预算，超时后结束当前步骤并按策略重试或降级。",
    "engineering:结果截断": "校验流式结束标记和结构化结果完整性，发生截断时仅重试失败步骤。",
    "reasoning:风险识别不足": "在风险识别策略中补齐当前场景的风险触发条件，并要求先完成风险分层。",
    "reasoning:未优先追问关键问题": "在场景策略中明确追问优先级，信息不足时先补齐关键事实再给建议。",
    "reasoning:错误分流": "校正意图和风险分流规则，使当前问题进入正确的咨询与处置路径。",
    "reasoning:错误选择行动路径": "为该类场景补充行动决策规则，明确何时追问、何时建议就医及何时给出方案。",
    "reasoning:禁忌或相互作用判断不足": "将禁忌、相互作用和治疗阶段校验置于方案生成前，阻断不适用建议。",
    "reasoning:医学事实识别错误": "在决策前结构化抽取症状、治疗阶段、药物和检查结果，并校验关键事实。",
    "reasoning:Timeline 时间顺序错误": "按事件时间重建 Timeline，区分既往、当前和计划事件后再判断。",
    "prompt:未说清红旗信号": "在回答中明确列出与当前问题相关的红旗信号及对应升级处置。",
    "prompt:未说明适用边界": "补充建议的适用人群、前提条件和不可替代医生决策的边界。",
    "prompt:系统提示词冲突": "消除系统提示词中的冲突规则，明确规则优先级、适用条件和行动边界。",
    "prompt:行动步骤不清晰": "按“下一步做什么、何时做、何时升级”的顺序输出可执行步骤。",
    "prompt:缺少适用条件或解释": "为建议补充适用条件、原因解释及与用户当前情况的关联。",
    "prompt:缺少共情与确认": "在回答中先确认用户感受与核心诉求，再给出有温度的建议。",
    "prompt:动态 Hook 异常": "核对动态 Hook 的触发条件、注入位置与规则内容，确保命中时在生成前生效。",
    "prompt:回答信息不完整": "增加回答关键要素清单，并在生成结束前完成完整性检查。",
    "knowledge:场景知识理解错误": "校正该场景的医学知识与业务语义，并在决策前核对适用条件。",
    "knowledge:用药禁忌应用错误": "修正用药禁忌与相互作用规则，并结合患者条件进行匹配。",
    "knowledge:治疗阶段判断错误": "统一治疗阶段识别规则，使用当前方案和 Timeline 共同确认阶段。",
    "knowledge:业务规则应用错误": "修正规则触发条件和优先级，确保规则只在适用场景生效。",
    "knowledge:规则冲突未消解": "为冲突规则建立明确优先级和适用边界，禁止同时生成矛盾结论。",
    "safety:关键事实前后矛盾": "在终答前核对关键事实与结论，阻断前后矛盾的内容发送。",
    "safety:遗漏风险提示": "在终答前检查当前场景所需的风险和红旗提示是否完整。",
    "safety:放出不安全建议": "在终答前增加安全守卫，命中风险、禁忌或红旗时阻断不安全建议。",
    "safety:未执行终答前检查": "在终答前校验关键事实、风险提示、消息分段和资源引用，并阻断不完整结果直接发送。",
    "safety:未触发兜底分流": "补齐异常或高风险场景的兜底分流条件，并确保命中后切换到安全路径。",
  };
  return actions[categoryKey] || "根据问题描述和直接证据修复对应环节。";
}

function cxAgentOptimizationActions(cluster: AttributionCluster, categoryKey: string) {
  const actions = [...new Set(
    (cluster.recommendations || [])
      .map((item) => String(item.action || "").trim())
      .filter(Boolean)
  )];
  return actions.length ? actions : [fallbackCxAgentOptimizationAction(categoryKey)];
}

type CxAgentClusterGroup = {
  priority: (typeof PRIORITY_ORDER)[number];
  category: ReturnType<typeof cxAgentSuggestionCategory>;
  clusters: AttributionCluster[];
  sampleIds: string[];
  deductionCount: number;
  descriptions: string[];
  actions: string[];
};

function groupedCxAgentClusters(clusters: AttributionCluster[]) {
  const groups = new Map<string, CxAgentClusterGroup>();
  clusters.forEach((cluster) => {
    const category = cxAgentSuggestionCategory({
      owner: cluster.owner,
      evaluation_issue_category: cluster.evaluation_issue_category,
      cause_code: cluster.cause_code,
      optimization_classification: cluster.optimization_classification,
      recommendations: cluster.recommendations,
    });
    const priority = (PRIORITY_ORDER.includes(cluster.priority as (typeof PRIORITY_ORDER)[number])
      ? cluster.priority
      : "P2") as (typeof PRIORITY_ORDER)[number];
    const key = `${priority}:${category.key}`;
    const group = groups.get(key) || {
      priority,
      category,
      clusters: [],
      sampleIds: [],
      deductionCount: 0,
      descriptions: [],
      actions: [],
    };
    group.clusters.push(cluster);
    group.sampleIds.push(...cluster.sample_ids);
    group.deductionCount += cluster.deduction_count;
    const descriptionCandidates = cluster.examples?.length
      ? cluster.examples
      : [cluster.summary || cluster.cause_label];
    descriptionCandidates.forEach((value) => {
      const description = humanizeAttributionText(value);
      if (description && !group.descriptions.includes(description)) {
        group.descriptions.push(description);
      }
    });
    cxAgentOptimizationActions(cluster, category.key).forEach((action) => {
      const readable = humanizeAttributionText(action);
      if (!group.actions.includes(readable)) group.actions.push(readable);
    });
    groups.set(key, group);
  });
  return [...groups.values()].map((group) => ({
    ...group,
    sampleIds: [...new Set(group.sampleIds)],
  }));
}

function NumberedAttributionPoints({
  items,
  emptyText,
}: {
  items: string[];
  emptyText: string;
}) {
  const values = [...new Set(items.map((value) => value.trim()).filter(Boolean))];
  if (!values.length) return <span>{emptyText}</span>;
  return (
    <ol className="attribution-numbered-points">
      {values.map((value) => (
        <li key={value}>{value}</li>
      ))}
    </ol>
  );
}

function CxAgentClusterPriorityGroups({
  clusters,
  task,
}: {
  clusters: AttributionCluster[];
  task: AttributionTask;
}) {
  const groups = groupedCxAgentClusters(clusters);
  return (
    <div className="attribution-suggestion-groups attribution-suggestion-groups--summary">
      {PRIORITY_ORDER.map((priority) => {
        const priorityGroups = groups.filter((group) => group.priority === priority);
        if (!priorityGroups.length) return null;
        return (
          <div className="attribution-priority-group" key={priority}>
            <div className="attribution-priority-group__head">
              <Tag color={priority === "P0" ? "red" : priority === "P1" ? "orange" : "blue"}>
                {priority} · {priorityDisplayName(priority)}
              </Tag>
              <span>{priorityGroups.length} 个问题分类</span>
            </div>
            <Collapse
              className="attribution-cluster-list attribution-cluster-list--nested"
              items={priorityGroups.map((group) => {
                return {
                  key: `${group.priority}-${group.category.key}`,
                  label: (
                    <div className="attribution-cluster-label">
                      <strong>问题分类：{group.category.label}</strong>
                      <span className="attribution-muted">
                        {group.sampleIds.length} 个 Case · {group.deductionCount} 项问题
                      </span>
                    </div>
                  ),
                  children: (
                    <div className="attribution-cluster-detail attribution-cluster-detail--optimization">
                      <div className="attribution-optimization-field">
                        <strong>通用问题描述：</strong>
                        <NumberedAttributionPoints
                          items={group.descriptions}
                          emptyText={`共同问题是“${group.category.label}”，当前还缺少可展示的具体表现。`}
                        />
                      </div>
                      <div className="attribution-optimization-field">
                        <strong>怎么优化：</strong>
                        <NumberedAttributionPoints
                          items={group.actions.map((action) =>
                            humanizeAttributionText(action)
                          )}
                          emptyText="暂无可执行的优化建议"
                        />
                      </div>
                      <div className="attribution-optimization-field">
                        <strong>关联 Case：</strong>
                        <CaseAttributionLinks task={task} sampleIds={group.sampleIds} />
                      </div>
                    </div>
                  ),
                };
              })}
            />
          </div>
        );
      })}
    </div>
  );
}

function fallbackEvaluationRecommendation(
  category: string | undefined,
  cluster: NonNullable<AttributionTask["diagnostic_summary"]>["clusters"][number]
): AttributionRecommendation {
  if (category === "benchmark_criteria_conflict") {
    return {
      priority: cluster.priority,
      target: "Benchmark 判据",
      action:
        "逐条核对检查点、扣分规则和推荐回答的适用条件；对同一行为结论相反的内容只保留一条明确规则，并补充边界条件。",
      expected_effect: "消除同一回答被相互矛盾的规则判定的情况。",
      verification: "用关联 Case 重新判分，并人工抽查规则、推荐回答和结论是否一致。",
      acceptance_criteria: "关联 Case 不再出现相同判据下的相反结论。",
    };
  }
  if (category === "annotation_rag_conflict") {
    return {
      priority: cluster.priority,
      target: "标注与 RAG 证据",
      action:
        "将标注结论与本 Case 的 RAG 原文逐条对照；无法由原文直接支持的结论改为待复核，或补充可追溯的权威来源。",
      expected_effect: "让标注、判分理由和医学证据使用同一事实依据。",
      verification: "复核关联 Case 的引用片段，确认每条扣分都能定位到支持它的证据。",
      acceptance_criteria: "每条保留的扣分均有可追溯的 RAG 或权威文献依据。",
    };
  }
  if (category === "missing_rag_reference") {
    return {
      priority: cluster.priority,
      target: "RAG 引用与证据采集",
      action:
        "为每个扣分项补齐可定位到原文片段的 RAG 文献、药品说明书或权威来源引用；引用缺失时将结论标记为待补证，不直接归责。",
      expected_effect: "先区分 RAG 事实依据与 Benchmark 判据，避免因来源缺失而误判。",
      verification: "补齐引用后重新归因，检查每个结论都能回链到原始 RAG 或权威来源。",
      acceptance_criteria: "关联 Case 不再处于“缺少 RAG 引用”状态，且每条扣分均有可追溯来源。",
    };
  }
  if (category === "evidence_gap") {
    return {
      priority: cluster.priority,
      target: "归因证据采集",
      action:
        "补齐当前扣分项缺失的对话原文、用户上下文、调用链或判分输入；证据不完整时保持待补证，不直接归责。",
      expected_effect: "避免因上下文或调用链缺失而误判。",
      verification: "补齐缺失证据后重新归因，确认结论可回链到真实输入。",
      acceptance_criteria: "关联 Case 不再处于“证据不足”状态，且结论可追溯。",
    };
  }
  return {
    priority: cluster.priority,
    target: "判分模型与规则",
    action:
      "将完整对话、用户档案、RAG 证据和扣分规则一起输入判分复核；明确条件限制和扣分档位，避免只依据局部文本扣分。",
    expected_effect: "减少漏读上下文、误用条件或扣分档位不一致的问题。",
    verification: "使用关联 Case 及同类边界 Case 回归，核对判分理由能对应原文和判据。",
    acceptance_criteria: "判分理由、原文证据和最终分数三者一致。",
  };
}

function EvaluationConflictGroup({
  task,
  title,
  countLabel,
  countColor,
  issueLabel,
  clusters,
  emptyDescription,
}: {
  task: AttributionTask;
  title: string;
  countLabel: string;
  countColor?: string;
  issueLabel: string;
  clusters: NonNullable<AttributionTask["diagnostic_summary"]>["clusters"];
  emptyDescription: string;
}) {
  const [expanded, setExpanded] = useState(false);
  if (!clusters.length) return null;
  return (
    <section className="attribution-evaluation-group">
      <div className="attribution-evaluation-group__head">
        <h5>{title}</h5>
        <Space size={4} wrap>
          <Tag color={countColor}>{countLabel}</Tag>
          {clusters.length ? (
            <Button
              type="link"
              size="small"
              aria-label={`${title}${expanded ? "收起" : "展开"}`}
              icon={expanded ? <UpOutlined /> : <DownOutlined />}
              onClick={() => setExpanded((current) => !current)}
            >
              {expanded ? "收起列表" : "展开列表"}
            </Button>
          ) : null}
        </Space>
      </div>
      {clusters.length ? (
        expanded ? (
          <List
            className="attribution-evaluation-conflicts"
            dataSource={clusters}
            renderItem={(cluster) => {
              const actions = cluster.recommendations?.length
                ? cluster.recommendations.map((item) => item.action).filter(Boolean)
                : [
                    fallbackEvaluationRecommendation(
                      cluster.evaluation_issue_category,
                      cluster
                    ).action,
                  ];
              return (
                <List.Item>
                  <div className="attribution-evaluation-conflict">
                    <div>
                      <strong>{issueLabel}：</strong>
                      {humanizeAttributionText(cluster.summary || cluster.cause_label)}
                    </div>
                    <div>
                      <strong>建议操作：</strong>
                      <div className="attribution-evaluation-conflict__actions">
                        {actions.map((action) => (
                          <div key={action}>{humanizeAttributionText(action)}</div>
                        ))}
                      </div>
                    </div>
                    <div className="attribution-evaluation-conflict__cases">
                      <strong>关联 Case：</strong>
                      <CaseAttributionLinks task={task} sampleIds={cluster.sample_ids} />
                    </div>
                  </div>
                </List.Item>
              );
            }}
          />
        ) : null
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={emptyDescription}
        />
      )}
    </section>
  );
}

export function AttributionTaskSummary({ task }: { task: AttributionTask }) {
  const [cxAgentExpanded, setCxAgentExpanded] = useState(false);
  const [selectedCxAgentPriorities, setSelectedCxAgentPriorities] = useState<
    (typeof PRIORITY_ORDER)[number][]
  >([...PRIORITY_ORDER]);
  const [evaluationExpanded, setEvaluationExpanded] = useState(false);
  const summary = task.diagnostic_summary;
  if (!summary?.available_results) {
    return (
      <DashPanel
        className="attribution-task-summary"
        title={
          <AttributionPanelHeading
            title="归因任务总结"
            subtitle="归因结果会逐条进入汇总，不需要等待整个任务结束"
          />
        }
      >
        <AttributionTaskProgress task={task} />
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="完成第一条 Case 归因后，这里会自动生成任务级优化总结"
        />
      </DashPanel>
    );
  }
  const clusters = summary.clusters || [];
  const cxAgentClusters = clusters.filter(
    (cluster) => cluster.category === "cx_agent_issue"
  );
  const filteredCxAgentClusters = cxAgentClusters.filter((cluster) =>
    selectedCxAgentPriorities.includes(
      cluster.priority as (typeof PRIORITY_ORDER)[number]
    )
  );
  const evaluationClusters = clusters.filter(
    (cluster) => cluster.category === "evaluation_review"
  );
  const benchmarkConflictClusters = evaluationClusters.filter(
    (cluster) =>
      cluster.evaluation_issue_category === "benchmark_criteria_conflict"
  );
  const annotationRagConflictClusters = evaluationClusters.filter(
    (cluster) => cluster.evaluation_issue_category === "annotation_rag_conflict"
  );
  const judgeLogicClusters = evaluationClusters.filter(
    (cluster) =>
      !["benchmark_criteria_conflict", "annotation_rag_conflict"].includes(
        cluster.evaluation_issue_category || "judge_logic_issue"
      )
  );
  const insufficientClusters = clusters.filter(
    (cluster) => cluster.category === "insufficient_evidence"
  );
  const otherEvidenceGapClusters = insufficientClusters;
  const deductionCount = (
    values: NonNullable<AttributionTask["diagnostic_summary"]>["clusters"]
  ) => values.reduce((total, cluster) => total + cluster.deduction_count, 0);
  const cxAgentIssueCount = deductionCount(cxAgentClusters);
  const evaluationReviewCount = deductionCount(evaluationClusters);
  const genericEvidenceGapCount = deductionCount(insufficientClusters);
  const hasEvaluationToolSuggestions =
    evaluationReviewCount > 0 || genericEvidenceGapCount > 0;
  const unassignedClusters = cxAgentClusters.filter(
    (cluster) =>
      selectedCxAgentPriorities.includes(
        cluster.priority as (typeof PRIORITY_ORDER)[number]
      ) && !cluster.dimensions.length
  );

  const dimensionItems: NonNullable<CollapseProps["items"]> =
    EVALUATION_DIMENSIONS.flatMap((dimension, dimensionIndex) => {
      const dimensionClusters = filteredCxAgentClusters.filter((cluster) =>
        cluster.dimensions.includes(dimension)
      );
      if (!dimensionClusters.length) return [];
      const affectedCases = new Set(
        dimensionClusters.flatMap((cluster) => cluster.sample_ids)
      );
      return [{
        key: dimension,
        label: (
          <div className="attribution-dimension-heading">
            <span className="attribution-dimension-index">
              {String(dimensionIndex + 1).padStart(2, "0")}
            </span>
            <strong>{dimensionDisplayName(dimension)}</strong>
            <span className="attribution-dimension-count">
              {groupedCxAgentClusters(dimensionClusters).length} 个通用优化点 · {affectedCases.size} 个 Case
            </span>
          </div>
        ),
        children: <CxAgentClusterPriorityGroups clusters={dimensionClusters} task={task} />,
      }];
    });

  if (unassignedClusters.length) {
    dimensionItems.push({
      key: "unassigned",
      label: (
        <div className="attribution-dimension-heading">
          <span className="attribution-dimension-index">—</span>
          <strong>尚未关联维度</strong>
          <span className="attribution-dimension-count">
            {groupedCxAgentClusters(unassignedClusters).length} 个通用优化点
          </span>
        </div>
      ),
      children: (
        <CxAgentClusterPriorityGroups clusters={unassignedClusters} task={task} />
      ),
    });
  }

  return (
    <DashPanel
      className="attribution-task-summary"
      title={
        <AttributionPanelHeading
          title="归因任务总结"
          subtitle="基于本次任务已完成的全部归因结果，将相似问题合并为可执行的通用优化点"
        />
      }
    >
      <Space size={8} wrap className="attribution-diagnostic-stats">
        <Tag color="blue">已分析 {summary.available_results} 条</Tag>
        <Tag color="red">cx-agent 问题 {cxAgentIssueCount} 项</Tag>
        <Tag color="orange">判分需复核 {evaluationReviewCount} 项</Tag>
        <Tag>证据不足 {genericEvidenceGapCount} 项</Tag>
      </Space>
      <AttributionTaskProgress task={task} />

      <section className="attribution-summary-section">
        <div className="attribution-summary-section__head">
          <div>
            <h4>cx-agent 优化建议</h4>
            <p>
              按八维评分标准聚合：同一维度、同一二级问题分类合并为通用优化点，并保留关联 Case。
            </p>
          </div>
          <Space size={6} wrap className="attribution-priority-filter">
            <Select
              aria-label="按问题等级筛选 cx-agent 优化点"
              mode="multiple"
              virtual={false}
              value={selectedCxAgentPriorities}
              options={PRIORITY_ORDER.map((priority) => ({
                label: priority,
                value: priority,
              }))}
              maxTagCount="responsive"
              placeholder="按问题等级筛选"
              onChange={(values: (typeof PRIORITY_ORDER)[number][]) =>
                setSelectedCxAgentPriorities(
                  values.length ? values : [...PRIORITY_ORDER]
                )
              }
            />
            <Tag color="red">
              {groupedCxAgentClusters(filteredCxAgentClusters).length} 个通用优化点
            </Tag>
            <Button
              type="link"
              size="small"
              aria-label={`cx-agent 优化建议${cxAgentExpanded ? "收起" : "展开"}`}
              icon={cxAgentExpanded ? <UpOutlined /> : <DownOutlined />}
              onClick={() => setCxAgentExpanded((current) => !current)}
            >
              {cxAgentExpanded ? "收起列表" : "展开列表"}
            </Button>
          </Space>
        </div>
        {cxAgentExpanded ? (
          <Collapse
            className="attribution-dimension-list"
            items={dimensionItems}
          />
        ) : null}
      </section>

      {hasEvaluationToolSuggestions ? (
        <section className="attribution-summary-section attribution-summary-section--evaluation">
        <div className="attribution-summary-section__head">
          <div>
            <h4>评测工具优化建议</h4>
            <p>
              将 Benchmark 内部冲突、标注与 RAG 冲突、其他判分复核和其他证据不足分开汇总，避免混在同一类里误修。
            </p>
          </div>
          <Space size={6}>
            <Tag color="orange">需要复核 {evaluationReviewCount}</Tag>
            <Tag>证据不足 {genericEvidenceGapCount}</Tag>
            <Button
              type="link"
              size="small"
              aria-label={`评测工具优化建议${evaluationExpanded ? "收起" : "展开"}`}
              icon={evaluationExpanded ? <UpOutlined /> : <DownOutlined />}
              onClick={() => setEvaluationExpanded((current) => !current)}
            >
              {evaluationExpanded ? "收起列表" : "展开列表"}
            </Button>
          </Space>
        </div>
        {evaluationExpanded ? (
          <div className="attribution-evaluation-groups">
            <EvaluationConflictGroup
              task={task}
              title="Benchmark 判据冲突"
              countLabel={`${deductionCount(benchmarkConflictClusters)} 项冲突 · ${benchmarkConflictClusters.length} 个通用问题`}
              countColor="red"
              issueLabel="判据冲突点"
              clusters={benchmarkConflictClusters}
              emptyDescription="本次任务没有发现 Benchmark 自身判据冲突"
            />
            <EvaluationConflictGroup
              task={task}
              title="判分点与 RAG 证据冲突"
              countLabel={`${deductionCount(annotationRagConflictClusters)} 项冲突 · ${annotationRagConflictClusters.length} 个通用问题`}
              countColor="volcano"
              issueLabel="判分点与 RAG 证据冲突点"
              clusters={annotationRagConflictClusters}
              emptyDescription="本次任务没有发现判分点与 RAG 证据冲突"
            />
            <EvaluationConflictGroup
              task={task}
              title="其他判分复核"
              countLabel={`${deductionCount(judgeLogicClusters)} 项待复核 · ${judgeLogicClusters.length} 个通用问题`}
              countColor="orange"
              issueLabel="判分复核点"
              clusters={judgeLogicClusters}
              emptyDescription="本次任务没有其他需要复核的判分问题"
            />
            <EvaluationConflictGroup
              task={task}
              title="其他证据不足"
              countLabel={`${deductionCount(otherEvidenceGapClusters)} 项证据不足 · ${otherEvidenceGapClusters.length} 个待补齐问题`}
              issueLabel="证据不足点"
              clusters={otherEvidenceGapClusters}
              emptyDescription="本次任务没有其他证据不足的问题"
            />
          </div>
        ) : null}
        </section>
      ) : null}
    </DashPanel>
  );
}

export interface RunAttributionTabProps {
  runId: number;
  loading?: boolean;
  latestTask?: AttributionTask | null;
  mode?: "list" | "detail";
  selectedTaskId?: number;
  onSelectedTaskIdChange?: (taskId: number | undefined) => void;
}

type AttributionModelSelection =
  | {
      mode: "rerun";
      task: AttributionTask;
      sampleIds: string[];
    }
  | {
      mode: "resume";
      task: AttributionTask;
    };

export function RunAttributionTab({
  runId,
  loading,
  latestTask,
  mode = "list",
  selectedTaskId,
  onSelectedTaskIdChange,
}: RunAttributionTabProps) {
  const detailMode = mode === "detail";
  const [tasks, setTasks] = useState<AttributionTask[]>([]);
  const [task, setTask] = useState<AttributionTask | null>(null);
  const [taskLoading, setTaskLoading] = useState(false);
  const [actionTaskId, setActionTaskId] = useState<number>();
  const [failureItem, setFailureItem] = useState<AttributionTaskItem | null>(
    null
  );
  const [selectedSampleIds, setSelectedSampleIds] = useState<string[]>([]);
  const [judgeModels, setJudgeModels] = useState<JudgeModel[]>([]);
  const [modelSelection, setModelSelection] =
    useState<AttributionModelSelection | null>(null);

  const loadTasks = useCallback(
    async (silent = false) => {
      try {
        const fetched = (await api.listAttributionTasks(runId)).map(
          normalizeTaskCounts
        );
        // 创建接口已经返回、列表接口尚未读到最新事务时，也不能把刚插入的
        // 任务从界面覆盖掉；一旦列表接口返回该任务，则以后端进度为准。
        const next =
          latestTask &&
          latestTask.run_id === runId &&
          !fetched.some((item) => item.id === latestTask.id)
            ? [
                { ...normalizeTaskCounts(latestTask), items: [] },
                ...fetched,
              ]
            : fetched;
        setTasks(next);
      } catch (error) {
        if (!silent) message.error(formatApiError(error, "加载归因任务失败"));
      }
    },
    [latestTask, runId]
  );

  const loadTask = useCallback(
    async (silent = false) => {
      if (!detailMode || !selectedTaskId) {
        setTask(null);
        return;
      }
      if (!silent) setTaskLoading(true);
      try {
        const next = normalizeTaskCounts(
          await api.getAttributionTask(runId, selectedTaskId)
        );
        setTask(next);
        // 明细响应已包含任务进度，直接同步列表卡片，轮询时不再重复请求列表接口。
        setTasks((current) =>
          current.map((item) =>
            item.id === next.id ? { ...next, items: [] } : item
          )
        );
      } catch (error) {
        if (!silent)
          message.error(formatApiError(error, "加载归因任务明细失败"));
      } finally {
        if (!silent) setTaskLoading(false);
      }
    },
    [detailMode, runId, selectedTaskId]
  );

  useEffect(() => {
    void loadTasks(false);
  }, [loadTasks]);
  useEffect(() => {
    if (!latestTask || latestTask.run_id !== runId) return;
    const next = normalizeTaskCounts(latestTask);
    setTasks((current) => [
      { ...next, items: [] },
      ...current.filter((item) => item.id !== next.id),
    ]);
  }, [latestTask, runId]);
  useEffect(() => {
    if (detailMode) void loadTask(false);
  }, [detailMode, loadTask]);
  useEffect(() => {
    setSelectedSampleIds([]);
  }, [task?.id]);
  const hasActiveTask = tasks.some(
    (item) => item.status === "queued" || item.status === "running"
  );
  usePollingTask(
    async () => {
      const selectedIsActive =
        detailMode && (task?.status === "queued" || task?.status === "running");
      if (selectedIsActive) await loadTask(true);
      else await loadTasks(true);
    },
    [detailMode, loadTask, loadTasks, task?.status],
    { enabled: hasActiveTask, immediate: false, intervalMs: 1500 }
  );
  const rerunSelectedCases = useCallback(async (
    source: AttributionTask,
    sampleIds: string[],
    judgeModelId: number
  ) => {
    if (sampleIds.length === 0) return;
    setActionTaskId(source.id);
    try {
      const next = normalizeTaskCounts(
        await api.rerunAttributionTask(runId, source.id, sampleIds, judgeModelId)
      );
      setTasks((current) =>
        current.map((item) =>
          item.id === next.id ? { ...next, items: [] } : item
        )
      );
      setTask(next);
      setModelSelection(null);
      setSelectedSampleIds([]);
      message.success(
        `归因任务 #${next.id} 已开始重试 ${sampleIds.length} 条用例`
      );
    } catch (error) {
      message.error(formatApiError(error, "重新归因失败"));
    } finally {
      setActionTaskId(undefined);
    }
  }, [runId]);

  const resumeTask = useCallback(
    async (source: AttributionTask, judgeModelId: number) => {
      setActionTaskId(source.id);
      try {
        const next = normalizeTaskCounts(
          await api.resumeAttributionTask(runId, source.id, judgeModelId)
        );
        setTasks((current) =>
          current.map((item) =>
            item.id === next.id ? { ...next, items: [] } : item
          )
        );
        if (detailMode && selectedTaskId === source.id) {
          setTask(next);
        }
        setModelSelection(null);
        message.success(
          `归因任务 #${next.id} 已继续：保留已完成结果，仅分析剩余用例`
        );
      } catch (error) {
        message.error(formatApiError(error, "继续归因失败"));
      } finally {
        setActionTaskId(undefined);
      }
    },
    [detailMode, runId, selectedTaskId]
  );

  const openModelSelection = useCallback(async (selection: AttributionModelSelection) => {
    if (judgeModels.length === 0) {
      try {
        const models = await api.listJudgeModels();
        setJudgeModels(models);
      } catch (error) {
        message.error(formatApiError(error, "加载归因模型失败"));
        return;
      }
    }
    setModelSelection(selection);
  }, [judgeModels.length]);

  const removeTask = useCallback(
    async (source: AttributionTask) => {
      setActionTaskId(source.id);
      try {
        await api.deleteAttributionTask(runId, source.id);
        const next = tasks.filter((item) => item.id !== source.id);
        setTasks(next);
        if (detailMode && selectedTaskId === source.id) {
          setTask(null);
          onSelectedTaskIdChange?.(undefined);
        }
        message.success(`归因任务 #${source.id} 已删除`);
      } catch (error) {
        message.error(formatApiError(error, "删除归因任务失败"));
      } finally {
        setActionTaskId(undefined);
      }
    },
    [detailMode, onSelectedTaskIdChange, runId, selectedTaskId, tasks]
  );

  const columns: ColumnsType<AttributionTaskItem> = useMemo(
    () => [
      { title: "Case ID", dataIndex: "sample_id", width: 130 },
      { title: "场景", dataIndex: "scenario", ellipsis: true },
      { title: "类别", dataIndex: "case_type", ellipsis: true },
      {
        title: "状态",
        dataIndex: "status",
        width: 110,
        render: (status: string, item) => (
          <Tooltip title={item.runtime_message || undefined}>
            <span>
              <AttributionStatusTag
                status={status}
                runtimeStatus={item.runtime_status}
                retryCount={item.retry_count}
              />
            </span>
          </Tooltip>
        ),
      },
      {
        title: "归因进度",
        key: "progress",
        width: 180,
        render: (_, item) => <AttributionItemProgress item={item} />,
      },
      {
        title: "操作",
        key: "action",
        width: 190,
        render: (_, item) => {
          if (item.attribution_available && task) {
            return (
              <Space className="attribution-item-actions" size={2}>
                <Link
                  className="dash-table__link attribution-view-link"
                  to={`/runs/${runId}/attribution-tasks/${task.id}/cases/${encodeURIComponent(item.sample_id)}`}
                >
                  <EyeOutlined /> 查看归因
                </Link>
                <Tooltip title="打开原用例详情">
                  <Link
                    className="attribution-case-link"
                    to={`/runs/${runId}/cases/${item.sample_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <LinkOutlined />
                  </Link>
                </Tooltip>
              </Space>
            );
          }
          if (item.error_msg) {
            return (
              <AttributionActionButton
                danger
                onClick={() => setFailureItem(item)}
              >
                查看失败原因
              </AttributionActionButton>
            );
          }
          return "—";
        },
      },
    ],
    [runId, task]
  );
  const taskColumns: ColumnsType<AttributionTask> = useMemo(
    () => [
      {
        title: "归因任务",
        key: "task",
        width: 176,
        render: (_, item) => (
          <div className="attribution-task-name">
            <strong>归因任务 #{item.id}</strong>
          </div>
        ),
      },
      {
        title: "分析模型",
        key: "model",
        width: 220,
        render: (_, item) => {
          const name = item.judge_model_name || `模型 #${item.judge_model_id}`;
          return (
            <Tooltip title={name}>
              <span className="attribution-model-name">{name}</span>
            </Tooltip>
          );
        },
      },
      {
        title: "用例范围",
        key: "scope",
        width: 160,
        render: (_, item) => (
          <div className="attribution-task-scope">
            <div>{item.total_count} 条不合格用例</div>
            {item.skipped_count ? (
              <div className="attribution-muted">
                跳过合格 {item.skipped_count} 条
              </div>
            ) : null}
          </div>
        ),
      },
      {
        title: "归因进度",
        key: "progress",
        width: 280,
        render: (_, item) => <AttributionTaskProgress task={item} />,
      },
      {
        title: "状态",
        dataIndex: "status",
        width: 110,
        render: (value: string) => <AttributionStatusTag status={value} task />,
      },
      {
        title: "创建时间",
        dataIndex: "created_at",
        width: 180,
        render: (value?: string | null) => formatApiDateTime(value),
      },
      {
        title: "操作",
        key: "action",
        fixed: "right",
        width: 270,
        render: (_, item) => {
          // 任务未处于执行中且并非已全部完成时，允许在原任务内继续。
          // 服务端会再按条目状态校验，仅将未成功的 Case 重新入队。
          const canResume =
            !hasActiveTask &&
            !["queued", "running", "success"].includes(item.status);
          const resumeButton = (
            <AttributionActionButton
              icon={<RedoOutlined />}
              disabled={hasActiveTask}
              loading={actionTaskId === item.id}
              onClick={() =>
                void openModelSelection({ mode: "resume", task: item })
              }
            >
              继续归因
            </AttributionActionButton>
          );
          return (
            <Space className="attribution-task-actions" size={2}>
              <Link
                className="dash-table__link attribution-action-button"
                to={`/runs/${runId}/attribution-tasks/${item.id}`}
              >
                <EyeOutlined /> 查看明细
              </Link>
              {canResume ? resumeButton : null}
              <Popconfirm
                title={
                  item.status === "queued" || item.status === "running"
                    ? "该任务仍在分析，删除会立即终止。确认删除？"
                    : "确认删除该归因任务及其全部结果？"
                }
                okText="删除"
                cancelText="取消"
                okButtonProps={{ danger: true }}
                onConfirm={() => void removeTask(item)}
              >
                <AttributionActionButton danger icon={<DeleteOutlined />}>
                  删除
                </AttributionActionButton>
              </Popconfirm>
            </Space>
          );
        },
      },
    ],
    [actionTaskId, hasActiveTask, openModelSelection, removeTask, runId]
  );
  const selectedCount = selectedSampleIds.length;
  const canSelectAll = Boolean(task?.items.length) && !hasActiveTask;
  const modelSelectionModal = (
    <AttributionTaskLaunchModal
      open={Boolean(modelSelection)}
      loading={actionTaskId === modelSelection?.task.id}
      requestedCount={
        modelSelection?.mode === "rerun"
          ? modelSelection.sampleIds.length
          : Math.max(
              0,
              (modelSelection?.task.total_count || 0) -
                (modelSelection?.task.success_count || 0)
            )
      }
      failedCount={1}
      judgeModels={judgeModels}
      mode={modelSelection?.mode || "rerun"}
      defaultJudgeModelId={modelSelection?.task.judge_model_id}
      onCancel={() => setModelSelection(null)}
      onSubmit={(judgeModelId) => {
        if (!modelSelection) return;
        if (modelSelection.mode === "rerun") {
          void rerunSelectedCases(
            modelSelection.task,
            modelSelection.sampleIds,
            judgeModelId
          );
        } else {
          void resumeTask(modelSelection.task, judgeModelId);
        }
      }}
    />
  );

  if (!detailMode)
    return (
      <div className="run-detail-page attribution-page">
        <DashPanel
          bodyClassName="dash-panel__body--flush"
          className="attribution-task-panel"
          title={
            <AttributionPanelHeading
              title="归因分析"
              subtitle="从筛选后的不合格用例发起任务；每完成一条会立即显示结果"
            />
          }
        >
          {loading ? (
            <div className="attribution-loading">
              <Spin size="large" />
            </div>
          ) : !tasks.length ? (
            <Empty description="暂无归因任务">
              <Typography.Text type="secondary">
                请在“用例明细”按筛选条件点击“开始归因分析”。
              </Typography.Text>
            </Empty>
          ) : (
            <Table
              className="dash-table attribution-task-table"
              rowKey="id"
              size="small"
              columns={taskColumns}
              dataSource={tasks}
              scroll={{ x: 1240 }}
              pagination={{
                pageSize: 10,
                showTotal: (total) => `共 ${total} 次归因`,
              }}
            />
          )}
          {modelSelectionModal}
        </DashPanel>
      </div>
    );

  return (
    <div className="run-detail-page attribution-page attribution-task-detail">
      {taskLoading ? (
        <div className="attribution-loading">
          <Spin />
        </div>
      ) : task ? (
        <>
          <AttributionTaskSummary task={task} />
          <DashPanel
            bodyClassName="dash-panel__body--flush"
            className="attribution-results-panel"
            title={
              <AttributionPanelHeading
                title={`任务 #${task.id} · 用例归因结果`}
                subtitle={`${TASK_STATUS[task.status]?.label || task.status} · ${task.judge_model_name}`}
              />
            }
            extra={
              <Space className="attribution-result-actions" size={4} wrap>
                <Button
                  size="small"
                  disabled={!canSelectAll}
                  onClick={() =>
                    setSelectedSampleIds(
                      task.items.map((item) => item.sample_id)
                    )
                  }
                >
                  全选
                </Button>
                {selectedCount > 0 ? (
                  <Button
                    size="small"
                    type="link"
                    onClick={() => setSelectedSampleIds([])}
                  >
                    取消选择
                  </Button>
                ) : null}
                <Tooltip
                  title={
                    hasActiveTask
                      ? "当前有归因任务正在执行，完成后可重新归因"
                      : undefined
                  }
                >
                  <span>
                    <Button
                      type="primary"
                      icon={<RedoOutlined />}
                      disabled={hasActiveTask || !selectedCount}
                      loading={actionTaskId === task.id}
                      onClick={() =>
                        void openModelSelection({
                          mode: "rerun",
                          task,
                          sampleIds: selectedSampleIds,
                        })
                      }
                    >
                      重新归因{selectedCount ? `（${selectedCount}）` : ""}
                    </Button>
                  </span>
                </Tooltip>
              </Space>
            }
          >
            <Table
              className="dash-table attribution-results-table"
              rowKey="sample_id"
              size="small"
              columns={columns}
              dataSource={task.items}
              rowSelection={{
                selectedRowKeys: selectedSampleIds,
                onChange: (keys) => setSelectedSampleIds(keys.map(String)),
                preserveSelectedRowKeys: true,
              }}
              pagination={{
                pageSize: 20,
                showTotal: (total) => `共 ${total} 条`,
              }}
            />
            {task.error_msg ? (
              <Alert
                type="error"
                showIcon
                message="任务异常"
                description={humanizeErrorText(task.error_msg, "归因任务执行失败，请稍后重试")}
                style={{ marginTop: 16 }}
              />
            ) : null}
          </DashPanel>
        </>
      ) : (
        <Empty description="未找到归因任务" />
      )}
      <Modal
        open={Boolean(failureItem)}
        title={
          failureItem
            ? `${failureItem.sample_id} · 归因失败原因`
            : "归因失败原因"
        }
        footer={
          <Button type="primary" onClick={() => setFailureItem(null)}>
            知道了
          </Button>
        }
        onCancel={() => setFailureItem(null)}
      >
        {failureItem ? (
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            {failureItem.error_msg.includes("服务重启") ? (
              <Alert
                type="warning"
                showIcon
                message="任务被服务重启中断"
                description="这不是用例或模型分析失败。重新发起归因即可，已完成的其他历史任务不会受影响。"
              />
            ) : failureItem.error_msg.includes("BadRequestError") &&
              task?.judge_model_name.toLowerCase().includes("kimi") ? (
              <Alert
                type="warning"
                showIcon
                message="当时的 Kimi K3 请求参数不兼容"
                description="当前已按 Kimi K3 默认要求启用思考模式并使用温度 1；可在下方用例列表勾选 Case 后重新归因。"
              />
            ) : (
              <Alert
                type="error"
                showIcon
                message="模型未能完成该用例的归因"
                description="请根据下方原始原因检查模型配置或稍后重新归因。"
              />
            )}
            <div className="attribution-failure-raw">
              <Typography.Text type="secondary">失败说明</Typography.Text>
              <Typography.Paragraph>
                {humanizeErrorText(failureItem.error_msg, "模型未能完成归因，请检查模型配置或稍后重试")}
              </Typography.Paragraph>
            </div>
          </Space>
        ) : null}
      </Modal>
      {modelSelectionModal}
    </div>
  );
}
