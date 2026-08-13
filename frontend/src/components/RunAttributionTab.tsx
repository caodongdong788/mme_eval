import {
  Alert,
  Button,
  Card,
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
  SafetyCertificateOutlined,
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
  humanizeAttributionText,
  humanizeEvidenceRef,
  informationStageDisplayName,
  priorityDisplayName,
  queryQualityDisplayName,
} from "../utils/attributionDisplay";
import { formatApiDateTime } from "../utils/datetime";
import { DashPanel } from "./DashPanel";

const OWNER_LABELS: Record<string, string> = {
  benchmark: "评测判据", judge: "判分模型", agent_prompt: "AI 助手提示词", orchestration: "对话流程编排",
  context_tool: "用户上下文工具", rag_corpus: "RAG 知识库", retriever: "RAG 召回",
  threshold: "RAG 阈值", reranker: "RAG 重排", generator: "回答生成", safety_policy: "安全策略", unknown: "待确认",
};
const RAG_LABELS: Record<string, string> = {
  not_needed: "无需 RAG", not_called: "应调用但未调用", failed: "调用失败", query_error: "查询词有误",
  corpus_gap: "知识库缺失", recall_error: "召回不足", threshold_error: "阈值过滤错误",
  candidate_or_rerank_error: "候选或重排错误", rerank_error: "重排选择错误",
  selected_not_used: "选中但未使用", selected_misinterpreted: "选中但理解错误",
  citation_mismatch: "引用与来源不一致", healthy: "RAG 链路正常", unknown: "证据不足",
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

function RecommendationList({ items }: { items: AttributionRecommendation[] }) {
  if (!items?.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无优化建议" />;
  return <List className="attribution-recommendations" dataSource={items} renderItem={(item) => (
    <List.Item><div><Space size={8} wrap><Tag color={item.priority === "P0" ? "red" : item.priority === "P1" ? "orange" : "blue"}>{priorityDisplayName(item.priority)}</Tag><strong>{humanizeAttributionText(item.target)}</strong></Space>
      <div className="attribution-recommendations__action">{humanizeAttributionText(item.action)}</div>
      {item.expected_effect ? <div className="attribution-muted">预期效果：{humanizeAttributionText(item.expected_effect)}</div> : null}
      <div className="attribution-muted">如何验证：{humanizeAttributionText(item.verification)}</div>
    </div></List.Item>
  )} />;
}

function DeductionPanel({ item, analyses }: { item: AttributionDeductionAnalysis; analyses: AttributionDeductionAnalysis[] }) {
  const validation = VALIDATION_LABELS[item.deduction_validation] || VALIDATION_LABELS.insufficient_evidence;
  const cause = item.primary_cause || { label: "待确认", owner: "unknown", confidence: 0 };
  return <div className="attribution-deduction">
    <div className="attribution-deduction__summary"><Space size={8} wrap><Tag color={validation.color}>{validation.label}</Tag><Tag color="purple">{humanizeAttributionText(cause.label || "原因待确认", analyses)}</Tag><Tag>责任环节：{OWNER_LABELS[cause.owner] || "待确认"}</Tag></Space>
      <div className="attribution-deduction__finding">{humanizeAttributionText(item.finding || cause.reason || "暂无结论", analyses)}</div>
      <div className="attribution-confidence"><span>归因置信度</span><Progress percent={confidencePercent(cause.confidence)} size="small" strokeColor="#7357ff" /></div>
    </div>
    <div className="attribution-section-title">因果链</div>
    {item.causal_chain?.length ? <Timeline items={item.causal_chain.map((step) => ({
      color: step.status === "fail" ? "red" : step.status === "pass" ? "green" : "gray",
      children: <div><strong>{STAGE_LABELS[step.stage] || "其他分析环节"}</strong><div>{humanizeAttributionText(step.finding, analyses)}</div>{step.evidence_refs?.length ? <div className="attribution-evidence">证据位置：{step.evidence_refs.map((ref) => humanizeEvidenceRef(ref, analyses)).join("、")}</div> : null}</div>,
    }))} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无完整因果链" />}
    <div className="attribution-section-title">RAG 诊断</div>
    <Descriptions size="small" column={{ xs: 1, md: 2, lg: 4 }}>
      <Descriptions.Item label="是否需要">{item.rag_diagnosis?.needed ? "需要" : "不需要"}</Descriptions.Item><Descriptions.Item label="实际调用">{item.rag_diagnosis?.called ? "已调用" : "未调用"}</Descriptions.Item>
      <Descriptions.Item label="查询质量">{queryQualityDisplayName(item.rag_diagnosis?.query_quality)}</Descriptions.Item><Descriptions.Item label="相关信息到达阶段">{informationStageDisplayName(item.rag_diagnosis?.relevant_information_stage)}</Descriptions.Item>
      <Descriptions.Item label="回答利用情况" span={2}>{answerUsageDisplayName(item.rag_diagnosis?.answer_usage)}</Descriptions.Item><Descriptions.Item label="结论" span={2}>{humanizeAttributionText(item.rag_diagnosis?.finding, analyses)}</Descriptions.Item>
    </Descriptions>
    <div className="attribution-section-title"><BulbOutlined /> 优化建议</div><RecommendationList items={item.recommendations || []} />
  </div>;
}

function AttributionSummarySection({
  title,
  color,
  items,
  empty,
  analyses,
}: {
  title: string;
  color: string;
  items: AttributionDeductionAnalysis[];
  empty: string;
  analyses: AttributionDeductionAnalysis[];
}) {
  return <div className="attribution-summary-section">
    <div className="attribution-summary-section__title"><Tag color={color}>{title} {items.length}</Tag></div>
    {items.length ? items.slice(0, 3).map((item) => <div className="attribution-summary-section__item" key={item.deduction_id}>
      <strong>{attributionDeductionLabel(item)}</strong>
      <span>{humanizeAttributionText(item.finding || item.primary_cause?.reason, analyses)}</span>
    </div>) : <div className="attribution-muted">{empty}</div>}
  </div>;
}

export interface AttributionSafetyContext {
  gatePassed?: boolean;
  dimensionScore?: number | null;
  dimensionMax?: number | null;
  dimensionReason?: string;
  guidelineDeductionCount?: number;
}

function AttributionSafetyOverview({
  context,
  analyses,
}: {
  context?: AttributionSafetyContext;
  analyses: AttributionDeductionAnalysis[];
}) {
  const safetyItems = analyses.filter((item) => item.dimension === "medical_safety");
  const supported = safetyItems.filter((item) => item.deduction_validation === "supported").length;
  const questionable = safetyItems.filter((item) => item.deduction_validation === "questionable").length;
  const insufficient = safetyItems.filter((item) => item.deduction_validation === "insufficient_evidence").length;
  const scoreKnown = typeof context?.dimensionScore === "number" && typeof context?.dimensionMax === "number";
  const dimensionPassed = scoreKnown && context.dimensionScore === context.dimensionMax;
  const guidelineCount = context?.guidelineDeductionCount ?? safetyItems.filter((item) => item.deduction_id.startsWith("guideline.")).length;

  let explanation = "本次没有医学安全相关扣分，未触发专项归因。";
  if (context?.gatePassed === false && dimensionPassed && guidelineCount > 0) {
    explanation = `八维评分中的“医学安全性”为满分，因此没有单独的维度扣分归因；但 ${guidelineCount} 条医学安全指南触发了安全门禁，导致最终医学安全性失败。归因分析已覆盖这些指南扣分。`;
  } else if (context?.gatePassed === false && safetyItems.length) {
    explanation = `本次医学安全门禁失败，归因分析已覆盖 ${safetyItems.length} 个医学安全相关扣分项。`;
  } else if (context?.gatePassed === true) {
    explanation = "本次医学安全门禁通过；若存在医学安全指南扣分，仍会在下方逐项展示复核结论。";
  } else if (safetyItems.length) {
    explanation = `归因分析已覆盖 ${safetyItems.length} 个医学安全相关扣分项。`;
  }

  const reviewLabel = [
    supported ? `${supported} 项成立` : "",
    questionable ? `${questionable} 项存疑` : "",
    insufficient ? `${insufficient} 项证据不足` : "",
  ].filter(Boolean).join("，") || "无医学安全扣分项";

  return <Card
    bordered={false}
    className={`attribution-safety-card ${context?.gatePassed === false ? "attribution-safety-card--failed" : ""}`}
    title={<Space><SafetyCertificateOutlined /><span>医学安全性专项分析</span></Space>}
    extra={context?.gatePassed === false ? <Tag color="red">安全门禁失败</Tag> : context?.gatePassed === true ? <Tag color="green">安全门禁通过</Tag> : null}
  >
    <Descriptions size="small" column={{ xs: 1, md: 2, lg: 4 }}>
      <Descriptions.Item label="最终安全门禁">{context?.gatePassed === false ? "失败" : context?.gatePassed === true ? "通过" : "暂无数据"}</Descriptions.Item>
      <Descriptions.Item label="八维医学安全性">{scoreKnown ? `${context.dimensionScore}/${context.dimensionMax}${dimensionPassed ? "（满分）" : ""}` : "暂无数据"}</Descriptions.Item>
      <Descriptions.Item label="安全指南扣分">{guidelineCount ? `${guidelineCount} 项` : "无"}</Descriptions.Item>
      <Descriptions.Item label="归因复核结论">{reviewLabel}</Descriptions.Item>
    </Descriptions>
    <Alert
      className="attribution-safety-card__explanation"
      type={context?.gatePassed === false ? "warning" : "info"}
      showIcon
      message={explanation}
      description={context?.dimensionReason ? `八维判分理由：${humanizeAttributionText(context.dimensionReason, analyses)}` : undefined}
    />
  </Card>;
}

export function AttributionDetail({ result, safetyContext }: { result: CaseAttribution; safetyContext?: AttributionSafetyContext }) {
  const analysis = result.analysis;
  if (!analysis) return null;
  const overall = analysis.overall;
  const rag = analysis.rag_overview;
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
    <div className="attribution-overview">
      <Card bordered={false} className="attribution-overview__main"><Space size={8} wrap><Tag color="purple">{overall?.primary_cause_label || "主要原因待确认"}</Tag><Tag>责任环节：{OWNER_LABELS[overall?.owner || "unknown"] || "待确认"}</Tag><Tag color={analysis.analysis_status === "complete" ? "green" : "orange"}>{analysis.analysis_status === "complete" ? "分析完整" : analysis.analysis_status === "partial" ? "部分分析" : "证据不足"}</Tag></Space>
        <div className="attribution-overview__headline-label">主要结论</div>
        <div className="attribution-overview__headline">
          <strong>共分析 {deductions.length} 个扣分项：{supported.length} 个扣分成立，{questionable.length} 个需要复核，{insufficient.length} 个证据不足。</strong>
          <span>{humanizeAttributionText(overall?.summary || "暂无综合结论", deductions)}</span>
        </div>
        <div className="attribution-confidence attribution-confidence--overview"><span>结论可信度</span><Progress percent={confidencePercent(overall?.confidence)} strokeColor="#7357ff" /></div>
      </Card>
      <Card bordered={false} title="医学知识检索（RAG）" className="attribution-overview__rag"><Space size={8} wrap><Tag color={rag?.enabled ? "blue" : "default"}>{rag?.enabled ? "已配置 RAG" : "未配置 RAG"}</Tag><Tag color={rag?.actually_called ? "green" : "default"}>{rag?.actually_called ? `实际调用 ${rag.call_count || 0} 次` : "本次未调用"}</Tag><Tag color={rag?.diagnosis === "healthy" ? "green" : rag?.diagnosis === "unknown" ? "default" : "orange"}>{RAG_LABELS[rag?.diagnosis || "unknown"] || "无法判断"}</Tag></Space><p>{humanizeAttributionText(rag?.summary || rag?.needed_reason || "暂无 RAG 结论", deductions)}</p></Card>
    </div>
    <AttributionSafetyOverview context={safetyContext} analyses={deductions} />
    <div className="attribution-summary-grid">
      <AttributionSummarySection title="确认存在的问题" color="red" items={supported} empty="没有确认成立的扣分项" analyses={deductions} />
      <AttributionSummarySection title="需要复核的判分" color="orange" items={questionable} empty="没有需要复核的判分" analyses={deductions} />
      <AttributionSummarySection title="证据不足" color="default" items={insufficient} empty="没有证据不足的项目" analyses={deductions} />
    </div>
    <div className="attribution-section-heading"><h3>逐项归因明细</h3><span>展开后查看原因、证据链、RAG 诊断和优化建议</span></div>
    <Collapse className="attribution-collapse" defaultActiveKey={deductions[0]?.deduction_id ? [deductions[0].deduction_id] : []} items={deductions.map((item) => ({ key: item.deduction_id, label: <Space wrap><strong>{attributionDeductionLabel(item)}</strong><Tag color={VALIDATION_LABELS[item.deduction_validation]?.color || "default"}>{VALIDATION_LABELS[item.deduction_validation]?.label || "证据不足"}</Tag><span>{humanizeAttributionText(item.primary_cause?.label || item.finding, deductions)}</span></Space>, children: <DeductionPanel item={item} analyses={deductions} /> }))} />
    {analysis.global_recommendations?.length ? <Card title="整体优化建议" bordered={false}><RecommendationList items={analysis.global_recommendations} /></Card> : null}
    {analysis.limitations?.length ? <Alert type="warning" showIcon message="本次分析仍缺少的证据" description={analysis.limitations.map((item) => humanizeAttributionText(item, deductions)).join("；")} /> : null}
    <div className="attribution-meta">分析模型：{result.metadata.model || "—"} · 分析时间：{formatApiDateTime(result.metadata.generated_at)}</div>
  </div>;
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
  const rerunTask = useCallback(async (source: AttributionTask) => {
    setActionTaskId(source.id);
    try {
      const next = normalizeTaskCounts(await api.rerunAttributionTask(runId, source.id));
      setTasks((current) => [
        { ...next, items: [] },
        ...current.filter((item) => item.id !== next.id),
      ]);
      setTask(next);
      onSelectedTaskIdChange(next.id);
      message.success(`已创建归因任务 #${next.id}`);
    } catch (error) {
      message.error(formatApiError(error, "重新归因失败"));
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
      width: 270,
      render: (_, item) => {
        const rerunButton = (
          <Button
            type="link"
            size="small"
            icon={<RedoOutlined />}
            disabled={hasActiveTask}
            loading={actionTaskId === item.id}
          >
            重新归因
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
            {hasActiveTask ? (
              <Tooltip title="当前有归因任务正在执行，完成后可重新归因">
                <span>{rerunButton}</span>
              </Tooltip>
            ) : (
              <Popconfirm
                title="重新归因会创建一个新任务，原任务和结果会保留。"
                okText="开始归因"
                cancelText="取消"
                onConfirm={() => void rerunTask(item)}
              >
                {rerunButton}
              </Popconfirm>
            )}
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
  ], [actionTaskId, hasActiveTask, onSelectedTaskIdChange, removeTask, rerunTask, selectedTaskId]);
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
    {taskLoading ? <div className="attribution-loading"><Spin /></div> : task ? <DashPanel title={<div><h3>任务 #{task.id} · 用例归因结果</h3><span className="dash-table-card__sub">{TASK_STATUS[task.status]?.label || task.status} · {task.judge_model_name}</span></div>}>
      <Table className="dash-table" rowKey="sample_id" size="small" columns={columns} dataSource={task.items} pagination={{ pageSize: 20, showTotal: (total) => `共 ${total} 条` }} />
      {task.error_msg ? <Alert type="error" showIcon message="任务异常" description={task.error_msg} style={{ marginTop: 16 }} /> : null}
    </DashPanel> : null}
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
              description="当前已修正为思考模式并使用 0.6 温度，模型连通性验证已通过；可在任务列表点击“重新归因”。"
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
