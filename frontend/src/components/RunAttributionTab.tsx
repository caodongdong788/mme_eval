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
  Space,
  Spin,
  Table,
  Tag,
  Timeline,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  BulbOutlined,
  DeleteOutlined,
  EyeOutlined,
  LinkOutlined,
  RedoOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  api,
  type AttributionDeductionAnalysis,
  type AttributionRecommendation,
  type AttributionTask,
  type AttributionTaskItem,
  type CaseAttribution,
  type CaseRow,
} from "../api";
import { formatApiError } from "../utils/apiError";
import {
  answerUsageDisplayName,
  attributionDeductionLabel,
  dimensionDisplayName,
  humanizeAttributionText,
  humanizeEvidenceRef,
  informationStageDisplayName,
  priorityDisplayName,
  queryQualityDisplayName,
} from "../utils/attributionDisplay";
import { formatApiDateTime } from "../utils/datetime";
import { DashPanel } from "./DashPanel";

const OWNER_LABELS: Record<string, string> = {
  benchmark: "评测判据", judge: "判分模型", agent_prompt: "提示词优化", orchestration: "对话流程编排",
  context_tool: "用户上下文工具", rag_corpus: "RAG 知识库", retriever: "RAG 召回",
  threshold: "RAG 阈值", reranker: "RAG 重排", generator: "回答生成", safety_policy: "安全策略", unknown: "待确认",
};
const STAGE_LABELS: Record<string, string> = {
  judge_validation: "扣分校验", context_fetch: "上下文读取", rag_decision: "RAG 调用决策",
  rag_query: "检索词生成", raw_recall: "原始召回", threshold: "阈值过滤", candidate: "候选生成",
  rerank: "重排选择", grounding: "证据利用", generation: "最终生成",
  patient_context_availability: "用户档案是否可用", context_usage: "用户信息使用情况",
  judge_verification: "判分依据复核", benchmark_validation: "评测判据复核",
  response_review: "回答内容核对", clarification: "追问策略",
};
const VALIDATION_LABELS: Record<string, { label: string; color: string }> = {
  supported: { label: "扣分成立", color: "red" },
  questionable: { label: "扣分存疑", color: "orange" },
  insufficient_evidence: { label: "证据不足", color: "default" },
};
const TASK_STATUS: Record<string, { label: string; color: string }> = {
  queued: { label: "排队中", color: "default" }, running: { label: "分析中", color: "processing" },
  success: { label: "已完成", color: "success" }, partial: { label: "部分完成", color: "warning" },
  failed: { label: "分析失败", color: "error" },
};

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
  { key: "prompt", label: "提示词优化", pattern: /提示词|prompt|agent_prompt/i },
  { key: "rag", label: "RAG 优化", pattern: /\brag\b|知识库|文献|检索|召回|重排|阈值/i },
  { key: "flow", label: "对话流程优化", pattern: /对话流程|流程编排|追问|orchestration/i },
  { key: "response", label: "回答策略优化", pattern: /回答策略|回答生成|生成模型|表达|\bagent\b|AI\s*助手/i },
  { key: "context", label: "上下文使用优化", pattern: /用户档案|用户上下文|上下文工具|context/i },
  { key: "safety", label: "安全策略优化", pattern: /安全策略|安全门禁|safety/i },
  { key: "benchmark", label: "评测判据优化", pattern: /benchmark|评测判据|评分标准|判据/i },
  { key: "judge_prompt", label: "判分提示词优化", pattern: /判分提示词|评测提示词|judge[ _-]?prompt/i },
  { key: "judge_context", label: "判分上下文优化", pattern: /判分上下文|评测上下文/i },
  { key: "judge_evidence", label: "判分证据核验", pattern: /判分证据|证据核验/i },
  { key: "judge_consistency", label: "判分一致性优化", pattern: /判分一致性|评分一致性/i },
  { key: "judge", label: "判分模型优化", pattern: /judge|判分模型|判分逻辑|评测模型/i },
  { key: "evidence", label: "证据采集优化", pattern: /证据采集|调用链|链路|审计|可观测|trace|observability/i },
] as const;

function recommendationDirection(item: AttributionRecommendation) {
  const target = item.target || "";
  const action = item.action || "";
  const judgeTarget = /judge|判分模型|判分逻辑|评测模型|判分提示词|评测提示词/i.test(target);
  if (judgeTarget) {
    if (/判分提示词|评测提示词|judge[ _-]?prompt/i.test(target)) return RECOMMENDATION_DIRECTIONS.find((item) => item.key === "judge_prompt");
    if (/注入|可见上下文|上下文输入/i.test(action)) return RECOMMENDATION_DIRECTIONS.find((item) => item.key === "judge_context");
    if (/全文检索|关键词|证据|核对|引用|命中|原文/i.test(action)) return RECOMMENDATION_DIRECTIONS.find((item) => item.key === "judge_evidence");
    if (/逐条对齐|一致性|自相矛盾|判据鼓励|评分标准/i.test(action)) return RECOMMENDATION_DIRECTIONS.find((item) => item.key === "judge_consistency");
    if (/提示词|指令|规则|必须|强制|不得/i.test(action)) return RECOMMENDATION_DIRECTIONS.find((item) => item.key === "judge_prompt");
    return RECOMMENDATION_DIRECTIONS.find((item) => item.key === "judge");
  }
  return RECOMMENDATION_DIRECTIONS.find((candidate) => candidate.pattern.test(target))
    || RECOMMENDATION_DIRECTIONS.find((candidate) => candidate.pattern.test(action));
}

function groupedRecommendations(items: AttributionRecommendation[]) {
  const groups = new Map<string, { key: string; label: string; items: AttributionRecommendation[] }>();
  items.forEach((item) => {
    const direction = recommendationDirection(item);
    const key = direction?.key || "other";
    const group = groups.get(key) || { key, label: direction?.label || "其他优化", items: [] };
    group.items.push(item);
    groups.set(key, group);
  });
  return [...groups.values()].sort((left, right) => {
    const leftIndex = RECOMMENDATION_DIRECTIONS.findIndex((item) => item.key === left.key);
    const rightIndex = RECOMMENDATION_DIRECTIONS.findIndex((item) => item.key === right.key);
    return (leftIndex < 0 ? Number.MAX_SAFE_INTEGER : leftIndex) - (rightIndex < 0 ? Number.MAX_SAFE_INTEGER : rightIndex);
  });
}

function RecommendationList({ items }: { items: AttributionRecommendation[] }) {
  if (!items?.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无优化建议" />;
  return <div className="attribution-recommendation-groups">
    {groupedRecommendations(items).map((group) => <section className="attribution-recommendation-group" key={group.key}>
      <div className="attribution-recommendation-group__title"><strong>{group.label}</strong><Tag>{group.items.length} 项</Tag></div>
      <List className="attribution-recommendations" dataSource={group.items} renderItem={(item) => (
        <List.Item><div><Tag color={item.priority === "P0" ? "red" : item.priority === "P1" ? "orange" : "blue"}>{priorityDisplayName(item.priority)}</Tag>
          <div className="attribution-recommendations__action">{humanizeAttributionText(item.action)}</div>
          {item.expected_effect ? <div className="attribution-muted">预期效果：{humanizeAttributionText(item.expected_effect)}</div> : null}
          {item.risk ? <div className="attribution-muted">修改风险：{humanizeAttributionText(item.risk)}</div> : null}
          <div className="attribution-muted">如何验证：{humanizeAttributionText(item.verification)}</div>
          {item.acceptance_criteria ? <div className="attribution-muted">验收标准：{humanizeAttributionText(item.acceptance_criteria)}</div> : null}
        </div></List.Item>
      )} />
    </section>)}
  </div>;
}

type AttributionModuleKind = "supported" | "questionable" | "insufficient";

const REQUIRED_INFORMATION_LABELS: Record<string, string> = {
  patient_context: "用户档案与历史事实",
  literature: "医学文献与指南",
  reasoning: "回答判断依据",
  clarification: "追问过程",
  safety_policy: "安全策略执行记录",
};

function DeductionPanel({ item, analyses, kind }: { item: AttributionDeductionAnalysis; analyses: AttributionDeductionAnalysis[]; kind: AttributionModuleKind }) {
  const validation = VALIDATION_LABELS[item.deduction_validation] || VALIDATION_LABELS.insufficient_evidence;
  const cause = item.primary_cause || { label: "待确认", owner: "unknown", confidence: 0 };
  const findingTitle = kind === "supported" ? "确认的问题" : kind === "questionable" ? "为什么需要复核" : "目前能得出的结论";
  const chainTitle = kind === "supported" ? "问题是怎么产生的" : kind === "questionable" ? "判分复核依据" : "现有证据检查";
  return <div className="attribution-deduction">
    <div className="attribution-gap-card">
      <div className="attribution-section-title">评测要求与实际差距</div>
      <Descriptions size="small" column={1} bordered>
        <Descriptions.Item label="期望行为">{humanizeAttributionText(item.observed_gap?.expected || item.rubric_contract?.expected_behavior?.join("；"), analyses)}</Descriptions.Item>
        <Descriptions.Item label="实际表现">{humanizeAttributionText(item.observed_gap?.actual, analyses)}</Descriptions.Item>
        <Descriptions.Item label="明确差距">{humanizeAttributionText(item.observed_gap?.gap || item.finding, analyses)}</Descriptions.Item>
        <Descriptions.Item label="直接证据">{item.observed_gap?.direct_evidence?.length ? item.observed_gap.direct_evidence.map((value) => humanizeAttributionText(value, analyses)).join("；") : "暂无可引用的直接证据"}</Descriptions.Item>
      </Descriptions>
    </div>
    <div className="attribution-deduction__summary">
      <div className="attribution-section-title">{findingTitle}</div>
      <Space size={8} wrap><Tag color={validation.color}>{validation.label}</Tag><Tag color="purple">{humanizeAttributionText(cause.label || "原因待确认", analyses)}</Tag><Tag>{kind === "insufficient" ? "暂不归责" : `责任环节：${OWNER_LABELS[cause.owner] || "待确认"}`}</Tag></Space>
      <div className="attribution-deduction__finding">{humanizeAttributionText(item.finding || cause.reason || "暂无结论", analyses)}</div>
      <div className="attribution-confidence"><span>归因置信度</span><Progress percent={confidencePercent(cause.confidence)} size="small" strokeColor="#7357ff" /></div>
    </div>
    <div className="attribution-section-title">{chainTitle}</div>
    {item.causal_chain?.length ? <Timeline items={item.causal_chain.map((step) => ({
      color: step.status === "fail" ? "red" : step.status === "pass" ? "green" : "gray",
      children: <div><strong>{STAGE_LABELS[step.stage] || "其他分析环节"}</strong><div>{humanizeAttributionText(step.finding, analyses)}</div>{step.evidence_refs?.length ? <div className="attribution-evidence">证据位置：{step.evidence_refs.map((ref) => humanizeEvidenceRef(ref, analyses)).join("、")}</div> : null}</div>,
    }))} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无完整因果链" />}
    {kind === "supported" && item.root_cause_test?.if_fixed ? <Alert
      type={item.root_cause_test.would_prevent_issue ? "success" : "warning"}
      showIcon
      message="根因反事实检查"
      description={<div><strong>如果修复：</strong>{humanizeAttributionText(item.root_cause_test.if_fixed, analyses)}<br /><strong>判断：</strong>{humanizeAttributionText(item.root_cause_test.reason, analyses)}</div>}
    /> : null}
    <div className="attribution-section-title">医学知识检索对本项的影响</div>
    <Descriptions size="small" column={{ xs: 1, md: 2, lg: 4 }}>
      <Descriptions.Item label="是否需要">{item.rag_diagnosis?.needed ? "需要" : "不需要"}</Descriptions.Item><Descriptions.Item label="实际调用">{item.rag_diagnosis?.called ? "已调用" : "未调用"}</Descriptions.Item>
      <Descriptions.Item label="查询质量">{queryQualityDisplayName(item.rag_diagnosis?.query_quality)}</Descriptions.Item><Descriptions.Item label="相关信息到达阶段">{informationStageDisplayName(item.rag_diagnosis?.relevant_information_stage)}</Descriptions.Item>
      <Descriptions.Item label="回答利用情况" span={2}>{answerUsageDisplayName(item.rag_diagnosis?.answer_usage)}</Descriptions.Item><Descriptions.Item label="结论" span={2}>{humanizeAttributionText(item.rag_diagnosis?.finding, analyses)}</Descriptions.Item>
    </Descriptions>
  </div>;
}

function isEvaluationRecommendation(item: AttributionRecommendation) {
  return /benchmark|judge|评测|判分|判据|评分/i.test(`${item.target} ${item.action}`);
}

function isEvidenceRecommendation(item: AttributionRecommendation) {
  return !isEvaluationRecommendation(item)
    && /证据采集|链路|审计|可观测|trace|observability|candidate_membership|上下文采集/i.test(item.target);
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

function fallbackRecommendation(kind: AttributionModuleKind, item: AttributionDeductionAnalysis): AttributionRecommendation {
  const label = attributionDeductionLabel(item);
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
  const required = (item.required_information || []).map((key) => REQUIRED_INFORMATION_LABELS[key] || key).join("、") || "完整调用链和判分依据";
  return {
    priority: "P1",
    target: "归因证据采集",
    action: `补齐“${label}”需要的${required}，证据齐全前不要将问题归责给 AI 助手或评测系统。`,
    expected_effect: "让后续归因可以形成可验证结论",
    verification: "补齐证据后重新归因，确认该项能进入“问题成立”或“判分需复核”。",
  };
}

function moduleRecommendations(
  kind: AttributionModuleKind,
  items: AttributionDeductionAnalysis[],
  globalItems: AttributionRecommendation[],
) {
  const own = items.flatMap((item) => item.recommendations || []);
  const combined = [...own, ...globalItems];
  const matched = combined.filter((item) => {
    if (kind === "supported") return !isEvaluationRecommendation(item) && !isEvidenceRecommendation(item);
    if (kind === "questionable") return isEvaluationRecommendation(item);
    return isEvidenceRecommendation(item);
  });
  return uniqueRecommendations(matched.length ? matched : items.map((item) => fallbackRecommendation(kind, item)));
}

function AttributionAnalysisModule({
  kind,
  title,
  description,
  items,
  allItems,
  globalRecommendations,
  limitations = [],
}: {
  kind: AttributionModuleKind;
  title: string;
  description: string;
  items: AttributionDeductionAnalysis[];
  allItems: AttributionDeductionAnalysis[];
  globalRecommendations: AttributionRecommendation[];
  limitations?: string[];
}) {
  const color = kind === "supported" ? "red" : kind === "questionable" ? "orange" : "default";
  const adviceTitle = kind === "supported" ? "优化建议" : kind === "questionable" ? "评测系统优化逻辑" : "需要补充的证据";
  const adviceDescription = kind === "supported"
    ? "以下建议只针对已确认的 AI 助手、RAG 或对话流程问题。"
    : kind === "questionable"
      ? "以下建议只针对 Benchmark 判据、判分模型和评测证据读取问题。"
      : "补齐证据后再判断责任归属，避免在证据不足时误改 AI 助手或评测规则。";
  const recommendations = moduleRecommendations(kind, items, globalRecommendations);
  return <section className={`attribution-module attribution-module--${kind}`}>
    <div className="attribution-module__header">
      <div><Space size={8}><h3>{title}</h3><Tag color={color}>{items.length} 项</Tag></Space><p>{description}</p></div>
    </div>
    {items.length ? <Collapse
      className="attribution-collapse attribution-module__items"
      items={items.map((item, index) => ({
        key: item.deduction_id,
        label: <div className="attribution-module__item-label"><strong>{index + 1}. {attributionDeductionLabel(item)}</strong><span>{humanizeAttributionText(item.finding || item.primary_cause?.label, allItems)}</span></div>,
        children: <DeductionPanel item={item} analyses={allItems} kind={kind} />,
      }))}
    /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={`暂无${title}`} />}
    {(recommendations.length || limitations.length) ? <div className="attribution-module__advice">
      <div className="attribution-module__advice-title"><BulbOutlined /><div><strong>{adviceTitle}</strong><span>{adviceDescription}</span></div></div>
      {recommendations.length ? <RecommendationList items={recommendations} /> : null}
      {limitations.length ? <Alert type="warning" showIcon message="当前缺失信息" description={limitations.map((item) => humanizeAttributionText(item, allItems)).join("；")} /> : null}
    </div> : null}
  </section>;
}

export function AttributionDetail({ result }: { result: CaseAttribution }) {
  const analysis = result.analysis;
  if (!analysis) return null;
  const deductions = [...(analysis.deduction_analyses || [])].sort((left, right) => {
    const leftSafety = left.dimension === "medical_safety" ? 0 : 1;
    const rightSafety = right.dimension === "medical_safety" ? 0 : 1;
    if (leftSafety !== rightSafety) return leftSafety - rightSafety;
    return left.deduction_id.localeCompare(right.deduction_id);
  });
  const supported = deductions.filter((item) => item.deduction_validation === "supported");
  const questionable = deductions.filter((item) => item.deduction_validation === "questionable");
  const insufficient = deductions.filter((item) => item.deduction_validation === "insufficient_evidence");
  return <div className="attribution-layout">
    {result.stale ? <Alert type="warning" showIcon message="用例证据已变化，当前结果可能过期" description="请从用例明细重新发起归因任务。" /> : null}
    {analysis.score_health && analysis.score_health.status !== "healthy" ? <Alert
      type={analysis.score_health.status === "invalid" ? "error" : "warning"}
      showIcon
      message={analysis.score_health.status === "invalid" ? "判分异常，暂不归责 cx-agent" : "判分需要复核"}
      description={<div><div>{analysis.score_health.summary}</div>{analysis.score_health.issues?.map((issue) => <div key={`${issue.code}-${issue.message}`}>· {humanizeAttributionText(issue.message, deductions)}</div>)}</div>}
    /> : null}
    <AttributionAnalysisModule
      kind="supported"
      title="cx-agent问题归因"
      description="这些问题有对话原文或调用链证据支持，应优先修复 AI 助手的回答、追问、RAG 使用或流程编排。"
      items={supported}
      allItems={deductions}
      globalRecommendations={analysis.global_recommendations || []}
    />
    <AttributionAnalysisModule
      kind="questionable"
      title="需要复核的判分"
      description="这些扣分与对话原文、用户档案或医学证据存在矛盾，先优化评测判据或判分逻辑，不应直接修改 AI 助手。"
      items={questionable}
      allItems={deductions}
      globalRecommendations={analysis.global_recommendations || []}
    />
    <AttributionAnalysisModule
      kind="insufficient"
      title="证据不足，暂不归责"
      description="当前证据无法判断是 AI 助手问题还是评测问题，需要先补齐调用链、RAG 审计或用户上下文。"
      items={insufficient}
      allItems={deductions}
      globalRecommendations={analysis.global_recommendations || []}
      limitations={analysis.limitations || []}
    />
    <div className="attribution-meta">分析模型：{result.metadata.model || "—"} · 分析时间：{formatApiDateTime(result.metadata.generated_at)}</div>
  </div>;
}

function TaskDiagnosticOverview({ task }: { task: AttributionTask }) {
  const summary = task.diagnostic_summary;
  if (!summary?.available_results) return null;
  const validation = summary.validation_counts || {};
  const clusters = summary.clusters || [];
  return <DashPanel title={<div><h3>任务级问题诊断</h3><span className="dash-table-card__sub">将相同根因跨 Case 合并，先处理影响面最大的系统问题</span></div>}>
    <Space size={8} wrap className="attribution-diagnostic-stats">
      <Tag color="blue">已分析 {summary.available_results} 条</Tag>
      <Tag color="red">cx-agent 问题 {validation.supported || 0} 项</Tag>
      <Tag color="orange">判分需复核 {validation.questionable || 0} 项</Tag>
      <Tag>证据不足 {validation.insufficient_evidence || 0} 项</Tag>
    </Space>
    {clusters.length ? <Collapse className="attribution-cluster-list" items={clusters.map((cluster, index) => ({
      key: `${cluster.category}-${cluster.cause_code}-${cluster.owner}-${index}`,
      label: <div className="attribution-cluster-label">
        <Space size={8} wrap>
          <Tag color={cluster.priority === "P0" ? "red" : cluster.priority === "P1" ? "orange" : "blue"}>{cluster.priority}</Tag>
          <strong>{humanizeAttributionText(cluster.cause_label)}</strong>
          <Tag>{cluster.case_count} 个 Case</Tag>
          <Tag>{cluster.deduction_count} 个问题</Tag>
          <span>{OWNER_LABELS[cluster.owner] || "待确认"}</span>
        </Space>
        <div className="attribution-muted">{humanizeAttributionText(cluster.summary)}</div>
      </div>,
      children: <div className="attribution-cluster-detail">
        <Descriptions size="small" column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="影响用例">{cluster.sample_ids.join("、")}</Descriptions.Item>
          <Descriptions.Item label="影响维度">{cluster.dimensions.map(dimensionDisplayName).join("、") || "未关联维度"}</Descriptions.Item>
          <Descriptions.Item label="平均置信度">{confidencePercent(cluster.confidence)}%</Descriptions.Item>
          <Descriptions.Item label="责任环节">{OWNER_LABELS[cluster.owner] || "待确认"}</Descriptions.Item>
        </Descriptions>
        <div className="attribution-section-title">优化方案</div>
        <RecommendationList items={cluster.recommendations || []} />
        {cluster.verification_plan?.acceptance_criteria?.length ? <Alert
          type="info"
          showIcon
          message="回归验收标准"
          description={cluster.verification_plan.acceptance_criteria.join("；")}
        /> : null}
      </div>,
    }))} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="已完成结果中暂无可聚类问题" />}
  </DashPanel>;
}

export interface RunAttributionTabProps {
  runId: number;
  runStatus: string;
  cases: CaseRow[];
  loading?: boolean;
  selectedTaskId?: number;
  onSelectedTaskIdChange: (taskId: number | undefined) => void;
}

export function RunAttributionTab({ runId, loading, selectedTaskId, onSelectedTaskIdChange }: RunAttributionTabProps) {
  const [tasks, setTasks] = useState<AttributionTask[]>([]);
  const [task, setTask] = useState<AttributionTask | null>(null);
  const [taskLoading, setTaskLoading] = useState(false);
  const [actionTaskId, setActionTaskId] = useState<number>();
  const [failureItem, setFailureItem] = useState<AttributionTaskItem | null>(null);
  const [selectedSampleIds, setSelectedSampleIds] = useState<string[]>([]);

  const loadTasks = useCallback(async (silent = false) => {
    try {
      const next = (await api.listAttributionTasks(runId)).map(normalizeTaskCounts);
      setTasks(next);
      if (!selectedTaskId && next[0]) onSelectedTaskIdChange(next[0].id);
    } catch (error) {
      if (!silent) message.error(formatApiError(error, "加载归因任务失败"));
    }
  }, [onSelectedTaskIdChange, runId, selectedTaskId]);

  const loadTask = useCallback(async (silent = false) => {
    if (!selectedTaskId) { setTask(null); return; }
    if (!silent) setTaskLoading(true);
    try {
      const next = normalizeTaskCounts(await api.getAttributionTask(runId, selectedTaskId));
      setTask(next);
      // 明细响应已包含任务进度，直接同步列表卡片，轮询时不再重复请求列表接口。
      setTasks((current) => current.map((item) => (
        item.id === next.id ? { ...next, items: [] } : item
      )));
    }
    catch (error) {
      if (!silent) message.error(formatApiError(error, "加载归因任务明细失败"));
    }
    finally {
      if (!silent) setTaskLoading(false);
    }
  }, [runId, selectedTaskId]);

  useEffect(() => { void loadTasks(false); }, [loadTasks]);
  useEffect(() => { void loadTask(false); }, [loadTask]);
  useEffect(() => { setSelectedSampleIds([]); }, [task?.id]);
  useEffect(() => {
    const active = tasks.some((item) => item.status === "queued" || item.status === "running");
    if (!active) return;
    const timer = window.setInterval(() => {
      const selectedIsActive = task?.status === "queued" || task?.status === "running";
      if (selectedIsActive) void loadTask(true);
      else void loadTasks(true);
    }, 1500);
    return () => window.clearInterval(timer);
  }, [loadTask, loadTasks, task?.status, tasks]);
  const rerunSelectedCases = useCallback(async () => {
    if (!task || selectedSampleIds.length === 0) return;
    setActionTaskId(task.id);
    try {
      const next = normalizeTaskCounts(await api.createAttributionTask(runId, {
        sample_ids: selectedSampleIds,
        judge_model_id: task.judge_model_id,
      }));
      setTasks((current) => [
        { ...next, items: [] },
        ...current.filter((item) => item.id !== next.id),
      ]);
      setTask(next);
      onSelectedTaskIdChange(next.id);
      setSelectedSampleIds([]);
      message.success(`已创建归因任务 #${next.id}，将重新分析 ${next.total_count} 条用例`);
    } catch (error) {
      message.error(formatApiError(error, "重新归因失败"));
    } finally {
      setActionTaskId(undefined);
    }
  }, [onSelectedTaskIdChange, runId, selectedSampleIds, task]);

  const resumeTask = useCallback(async (source: AttributionTask) => {
    setActionTaskId(source.id);
    try {
      const next = normalizeTaskCounts(await api.resumeAttributionTask(runId, source.id));
      setTasks((current) => current.map((item) => item.id === next.id ? { ...next, items: [] } : item));
      setTask(next);
      onSelectedTaskIdChange(next.id);
      message.success(`归因任务 #${next.id} 已继续：保留已完成结果，仅分析剩余用例`);
    } catch (error) {
      message.error(formatApiError(error, "继续归因失败"));
    } finally {
      setActionTaskId(undefined);
    }
  }, [onSelectedTaskIdChange, runId]);

  const removeTask = useCallback(async (source: AttributionTask) => {
    setActionTaskId(source.id);
    try {
      await api.deleteAttributionTask(runId, source.id);
      const next = tasks.filter((item) => item.id !== source.id);
      setTasks(next);
      if (selectedTaskId === source.id) {
        setTask(null);
        onSelectedTaskIdChange(next[0]?.id);
      }
      message.success(`归因任务 #${source.id} 已删除`);
    } catch (error) {
      message.error(formatApiError(error, "删除归因任务失败"));
    } finally {
      setActionTaskId(undefined);
    }
  }, [onSelectedTaskIdChange, runId, selectedTaskId, tasks]);

  const columns: ColumnsType<AttributionTaskItem> = useMemo(() => [
    { title: "Case ID", dataIndex: "sample_id", width: 130 },
    { title: "场景", dataIndex: "scenario", ellipsis: true },
    { title: "类别", dataIndex: "case_type", ellipsis: true },
    { title: "状态", dataIndex: "status", width: 110, render: (status) => <Tag color={status === "success" ? "success" : status === "failed" ? "error" : status === "running" ? "processing" : "default"}>{status === "success" ? "已完成" : status === "failed" ? "失败" : status === "running" ? "分析中" : "排队中"}</Tag> },
    { title: "操作", key: "action", width: 190, render: (_, item) => item.attribution_available && task ? <Space size={8}><Link className="dash-table__link attribution-view-link" to={`/runs/${runId}/attribution-tasks/${task.id}/cases/${encodeURIComponent(item.sample_id)}`}><EyeOutlined /> 查看归因</Link><Tooltip title="打开原用例详情"><Link to={`/runs/${runId}/cases/${item.sample_id}`} state={{ from: { to: `/runs/${runId}`, state: { tab: "attribution", attributionTaskId: task.id }, label: "归因分析" } }}><LinkOutlined /></Link></Tooltip></Space> : item.error_msg ? <Button type="link" danger size="small" onClick={() => setFailureItem(item)}>查看失败原因</Button> : "—" },
  ], [runId, task]);
  const hasActiveTask = tasks.some((item) => item.status === "queued" || item.status === "running");
  const taskColumns: ColumnsType<AttributionTask> = useMemo(() => [
    {
      title: "归因任务",
      key: "task",
      width: 150,
      render: (_, item) => (
        <div className="attribution-task-name">
          <strong>归因任务 #{item.id}</strong>
          {item.id === selectedTaskId ? <Tag color="purple">当前查看</Tag> : null}
        </div>
      ),
    },
    {
      title: "分析模型",
      key: "model",
      width: 190,
      render: (_, item) => item.judge_model_name || `模型 #${item.judge_model_id}`,
    },
    {
      title: "用例范围",
      key: "scope",
      width: 160,
      render: (_, item) => (
        <div>
          <div>{item.total_count} 条不合格用例</div>
          {item.skipped_count ? <div className="attribution-muted">跳过合格 {item.skipped_count} 条</div> : null}
        </div>
      ),
    },
    {
      title: "归因进度",
      key: "progress",
      width: 300,
      render: (_, item) => {
        const runningCount = item.running_count || 0;
        const pendingCount = Number.isFinite(item.pending_count)
          ? item.pending_count
          : Math.max(0, item.total_count - item.completed_count - runningCount);
        const enteredCount = Math.min(
          item.total_count,
          item.completed_count + runningCount,
        );
        const percent = item.total_count
          ? Math.round(enteredCount / item.total_count * 100)
          : 0;
        return (
          <div className="attribution-task-progress">
            <Progress
              percent={percent}
              size="small"
              status={item.status === "failed" ? "exception" : item.status === "success" ? "success" : "active"}
              strokeColor={item.status === "partial" ? "#d89614" : undefined}
            />
            <div className="attribution-muted">
              已完成 {item.completed_count}/{item.total_count}
              {runningCount ? ` · 分析中 ${runningCount}` : ""}
              {pendingCount ? ` · 等待 ${pendingCount}` : ""}
              {item.failed_count ? ` · 失败 ${item.failed_count}` : ""}
            </div>
          </div>
        );
      },
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 110,
      render: (value: string) => {
        const status = TASK_STATUS[value] || TASK_STATUS.failed;
        return <Tag color={status.color}>{status.label}</Tag>;
      },
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
      width: 340,
      render: (_, item) => {
        // 任务未处于执行中且并非已全部完成时，允许在原任务内继续。
        // 服务端会再按条目状态校验，仅将未成功的 Case 重新入队。
        const canResume = !hasActiveTask
          && !["queued", "running", "success"].includes(item.status);
        const resumeButton = (
          <Button
            type="link"
            size="small"
            icon={<RedoOutlined />}
            disabled={hasActiveTask}
            loading={actionTaskId === item.id}
          >
            继续归因
          </Button>
        );
        return (
          <Space size={2}>
            <Button
              type="link"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => onSelectedTaskIdChange(item.id)}
            >
              查看明细
            </Button>
            {canResume ? (
              <Popconfirm
                title={`保留已完成的 ${item.success_count} 条归因结果，仅继续其余 ${item.total_count - item.success_count} 条用例。`}
                okText="继续归因"
                cancelText="取消"
                onConfirm={() => void resumeTask(item)}
              >
                {resumeButton}
              </Popconfirm>
            ) : null}
            <Popconfirm
              title={item.status === "queued" || item.status === "running" ? "该任务仍在分析，删除会立即终止。确认删除？" : "确认删除该归因任务及其全部结果？"}
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={() => void removeTask(item)}
            >
              <Button type="link" danger size="small" icon={<DeleteOutlined />}>删除</Button>
            </Popconfirm>
          </Space>
        );
      },
    },
  ], [actionTaskId, hasActiveTask, onSelectedTaskIdChange, removeTask, resumeTask, selectedTaskId]);
  return <div className="run-detail-page">
    <DashPanel title={<div><h3>归因分析</h3><span className="dash-table-card__sub">从筛选后的不合格用例发起任务；每完成一条会立即显示结果</span></div>}>
      {loading ? <div className="attribution-loading"><Spin size="large" /></div> : !tasks.length ? <Empty description="暂无归因任务"><Typography.Text type="secondary">请在“用例明细”按筛选条件点击“开始归因分析”。</Typography.Text></Empty> : <Table
        className="dash-table attribution-task-table"
        rowKey="id"
        size="middle"
        columns={taskColumns}
        dataSource={tasks}
        rowClassName={(item) => item.id === selectedTaskId ? "attribution-task-row--active" : ""}
        scroll={{ x: 1380 }}
        pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 次归因` }}
      />}
    </DashPanel>
    {taskLoading ? <div className="attribution-loading"><Spin /></div> : task ? <>
    <TaskDiagnosticOverview task={task} />
    <DashPanel title={<div><h3>任务 #{task.id} · 用例归因结果</h3><span className="dash-table-card__sub">{TASK_STATUS[task.status]?.label || task.status} · {task.judge_model_name}</span></div>} extra={<Space size={8}>
      <Button size="small" disabled={!task.items.length || hasActiveTask} onClick={() => setSelectedSampleIds(task.items.map((item) => item.sample_id))}>全选全部</Button>
      <Button size="small" disabled={!selectedSampleIds.length} onClick={() => setSelectedSampleIds([])}>取消选择</Button>
      <Tooltip title={hasActiveTask ? "当前有归因任务正在执行，完成后可重新归因" : undefined}>
        <span><Popconfirm
          title={`将按当前模型创建新的归因任务，重新分析已选 ${selectedSampleIds.length} 条用例；原任务结果会保留。`}
          okText="开始归因"
          cancelText="取消"
          disabled={hasActiveTask || !selectedSampleIds.length}
          onConfirm={() => void rerunSelectedCases()}
        ><Button type="primary" icon={<RedoOutlined />} disabled={hasActiveTask || !selectedSampleIds.length} loading={actionTaskId === task.id}>重新归因{selectedSampleIds.length ? `（${selectedSampleIds.length}）` : ""}</Button></Popconfirm></span>
      </Tooltip>
    </Space>}>
      <Table
        className="dash-table"
        rowKey="sample_id"
        size="small"
        columns={columns}
        dataSource={task.items}
        rowSelection={{
          selectedRowKeys: selectedSampleIds,
          onChange: (keys) => setSelectedSampleIds(keys.map(String)),
          preserveSelectedRowKeys: true,
        }}
        pagination={{ pageSize: 20, showTotal: (total) => `共 ${total} 条` }}
      />
      {task.error_msg ? <Alert type="error" showIcon message="任务异常" description={task.error_msg} style={{ marginTop: 16 }} /> : null}
    </DashPanel></> : null}
    <Modal
      open={Boolean(failureItem)}
      title={failureItem ? `${failureItem.sample_id} · 归因失败原因` : "归因失败原因"}
      footer={<Button type="primary" onClick={() => setFailureItem(null)}>知道了</Button>}
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
          ) : failureItem.error_msg.includes("BadRequestError") && task?.judge_model_name.toLowerCase().includes("kimi") ? (
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
            <Typography.Text type="secondary">原始错误</Typography.Text>
            <Typography.Paragraph copyable>{failureItem.error_msg}</Typography.Paragraph>
          </div>
        </Space>
      ) : null}
    </Modal>
  </div>;
}
