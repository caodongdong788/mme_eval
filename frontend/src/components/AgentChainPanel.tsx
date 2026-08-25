import {
  Alert,
  Button,
  Empty,
  Modal,
  Space,
} from "antd";
import { useState } from "react";
import {
  BranchesOutlined,
  DatabaseOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { DashPanel } from "./DashPanel";
import { AccountInitializationDetails } from "./ConversationContextReferences";
import {
  accountInitializationModules,
  type ConversationContextInitialState,
} from "../utils/conversationContext";

interface AgentChainNode {
  id: string;
  trace_id?: string;
  parent_id?: string | null;
  type?: string;
  name?: string;
  start_time?: string | null;
  duration_ms?: number | null;
  level?: string | null;
  status_message?: string | null;
  model?: string | null;
  input?: unknown;
  output?: unknown;
  metadata?: Record<string, unknown>;
  usage?: Record<string, unknown>;
}

interface ChainStep {
  id: string;
  title: string;
  category: "agent" | "model" | "source" | "risk" | "action" | "tool" | "span";
  summary: string;
  duration_ms?: number | null;
  status: "success" | "failed";
}

interface SourceSummary {
  key: string;
  label: string;
  status: "unused" | "injected" | "inactive" | "listed" | "read" | "queried" | "hit" | "miss" | "failed";
  summary: string;
  calls: number;
  count: number;
  details: string[];
  query?: unknown;
  mode?: string;
  metrics?: {
    searched?: number | null;
    qualified?: number | null;
    candidates?: number | null;
    selected?: number | null;
    threshold?: number | null;
  };
  rag_audit?: RagAuditCall[];
}

interface RagSource {
  id?: string;
  title?: string;
  doi?: string;
  journal?: string;
  pubYear?: number | string;
  score?: number;
  articleClass?: string;
  sourceTier?: string;
  confidenceLevel?: string;
  chunks?: Array<{
    title?: string;
    content?: string;
    sectionName?: string;
    score?: number;
    sourceRank?: number;
    chunkType?: string;
    raw?: Record<string, unknown>;
  }>;
}

export interface RagAuditCall {
  id: string;
  status: "available" | "truncated";
  unavailable_reason?: string;
  original_query?: string;
  rewritten_query?: string;
  mode?: string;
  counts?: SourceSummary["metrics"];
  all_sources?: RagSource[];
  qualified_sources?: RagSource[];
  candidate_sources?: RagSource[];
  selected_sources?: RagSource[];
}

interface RiskSummary {
  level: string;
  category: string;
  symptom: string;
  reason: string;
  status: "success" | "failed";
}

interface ActionSummary {
  tool: string;
  label: string;
  summary: string;
  status: "success" | "failed";
}

interface QualitySummary {
  total_duration_ms?: number | null;
  model_calls: number;
  tool_calls: number;
  tool_successes: number;
  tool_failures: number;
  models: string[];
  providers: string[];
  input_tokens: number;
  cached_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cache_hit_rate?: number | null;
  retry_count: number;
  anomalies: string[];
  errors: string[];
}

interface AgentChainSummary {
  steps: ChainStep[];
  sources: SourceSummary[];
  risks: RiskSummary[];
  actions: ActionSummary[];
  quality: QualitySummary;
}

interface AgentChainSnapshot {
  status?: "synced" | "partial" | "pending" | "failed" | "unconfigured";
  synced_at?: string;
  trace_ids?: string[];
  traces?: Array<{ trace_id?: string; trace_url?: string | null }>;
  nodes?: AgentChainNode[];
  summary?: AgentChainSummary;
  error?: string | null;
}

type AssertionType = "tool_call" | "retrieval" | "transcript";

export interface CaseEvaluationAssertion {
  id?: string;
  type?: AssertionType;
  description?: string;
  name?: string;
  contains?: string;
  min_count?: number;
  scope?: string;
  match_mode?: "exact" | "semantic";
  dimensions?: string[];
  deduction?: number;
  model_comparison_dimensions?: string[];
  model_comparison_deduction?: number;
}

export interface AssertionVerdict {
  name: string;
  passed?: boolean;
  reason?: string;
  evidence?: string[];
  details?: Record<string, unknown>;
}

interface EvaluationIdentity {
  login_account?: string;
  verification_code?: string;
  test_user_id?: string;
  reset_at?: string;
  reset_status?: string;
  cx_session_id?: string;
  user_profile?: Record<string, unknown>;
  profile_after_reset?: Record<string, unknown>;
  initial_state?: CaseInitialState;
  system_prompt_enabled?: boolean;
  response_preference?: {
    status?: "success" | "failed" | "inactive_system_prompt" | "not_configured";
    configuredCount?: number;
    loaded?: boolean;
    effective?: boolean;
  };
}

type CaseInitialState = ConversationContextInitialState;

export interface AgentChainTrace {
  langfuse_trace_url?: string | null;
  langfuse_trace_ids?: string[];
  evaluation_identity?: EvaluationIdentity;
  agent_chain?: AgentChainSnapshot;
}

const sourceStatusLabels: Record<SourceSummary["status"], string> = {
  unused: "未调用",
  injected: "已注入",
  inactive: "未生效",
  listed: "仅查看目录",
  read: "已读取",
  queried: "已查询",
  hit: "已命中",
  miss: "未命中",
  failed: "调用失败",
};

const assertionTypeLabels: Record<AssertionType, string> = {
  tool_call: "工具调用",
  retrieval: "数据命中",
  transcript: "回答要求",
};

const agentDimensionLabels: Record<string, string> = {
  medical_safety: "医学安全性",
  professional_accuracy: "专业准确性与边界",
  clinical_reasoning: "临床推理与追问",
  personalization: "上下文利用与个性化",
  feasibility: "方案可行性与依从性",
  empathy: "共情与情绪承接",
  execution: "可执行性",
  communication: "沟通表达",
  medical_knowledge_reasoning: "医学知识与临床推理",
  factuality_hallucination: "事实可靠性与幻觉控制",
  instruction_following: "指令遵循与产品边界",
  context_personalization: "上下文利用与个性化",
  tool_use: "工具选择与调用执行",
  multimodal_understanding: "图像与多模态理解",
  empathy_communication: "共情与患者沟通",
  multi_turn_consistency: "多轮一致性与状态保持",
};

const profileLabels: Record<string, string> = {
  nickname: "称呼",
  treatment_stage: "治疗阶段",
  disease: "疾病",
  diagnosis: "诊断",
  medication: "用药",
  medications: "用药",
  preferences: "偏好",
};

const legacyEvaluationLoginAccounts: Record<string, string> = {
  "00000000-0000-0000-0000-000000000101": "+8610000000101",
  "00000000-0000-0000-0000-000000000102": "+8610000000102",
  "00000000-0000-0000-0000-000000000103": "+8610000000103",
};

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function inlineText(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join("、");
  if (value && typeof value === "object") {
    return Object.entries(record(value)).map(([key, item]) => `${key}: ${inlineText(item)}`).join("；");
  }
  return String(value ?? "—");
}

function hasContent(value: unknown): boolean {
  if (value === null || value === undefined || value === "") return false;
  if (Array.isArray(value)) return value.some(hasContent);
  if (typeof value === "object") return Object.values(record(value)).some(hasContent);
  return true;
}

function responsePreferencePresentation(
  identity: EvaluationIdentity,
  initialState?: CaseInitialState,
): { label: string; tone: "success" | "error" | "warning" | "muted" } | null {
  const runtime = identity.response_preference;
  const configuredCount = Number(runtime?.configuredCount ?? initialState?.response_preferences?.length ?? 0);
  if (!runtime && configuredCount <= 0) return null;
  if (runtime?.status === "success" && runtime.effective) {
    return { label: "初始化成功", tone: "success" };
  }
  if (runtime?.status === "inactive_system_prompt") {
    return { label: "未生效（系统提示词关闭）", tone: "warning" };
  }
  if (runtime?.status === "failed") {
    return { label: "初始化失败", tone: "error" };
  }
  if (runtime?.status === "not_configured") {
    return { label: "未配置", tone: "muted" };
  }
  return { label: "无法确认", tone: "muted" };
}

function displayId(value?: string): string {
  if (!value) return "—";
  return value;
}

function loginAccount(identity: EvaluationIdentity): string {
  return identity.login_account
    || legacyEvaluationLoginAccounts[identity.test_user_id || ""]
    || "—";
}

function formatDuration(value?: number | null): string {
  if (value == null) return "—";
  return value >= 1000 ? `${(value / 1000).toFixed(1)} 秒` : `${Math.round(value)} ms`;
}

function formatCount(value?: number | null): string {
  if (value == null) return "—";
  return value >= 10000 ? `${(value / 1000).toFixed(1)}k` : value.toLocaleString("zh-CN");
}

function statusAlert(chain: AgentChainSnapshot) {
  if (chain.status === "synced") return null;
  const type = chain.status === "partial" || chain.status === "pending" ? "warning" : "info";
  const label = {
    partial: "部分 Trace 已同步",
    pending: "Langfuse 链路仍在写入，正在补同步",
    failed: "Langfuse 链路同步失败",
    unconfigured: "Langfuse 读取尚未配置",
  }[chain.status || "failed"];
  return <Alert type={type} showIcon message={label} description={chain.error || undefined} />;
}

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="agent-insight-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {hint ? <small>{hint}</small> : null}
    </div>
  );
}

function ContextCard({
  initialState,
  fallbackProfile,
}: {
  initialState?: CaseInitialState;
  fallbackProfile: Record<string, unknown>;
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const state = initialState || { user_profile: fallbackProfile };
  const modules = accountInitializationModules(state);
  if (!modules.length) return null;
  return (
    <section className="agent-insight-block agent-profile-card">
      <header><UserOutlined /><strong>账号初始化数据</strong><span>{modules.length} 个模块</span></header>
      <div className="agent-context-summary">
        {modules.map((module) => <div key={module.key}><strong>{module.label}</strong><span>{module.entries.length} 项，已初始化</span></div>)}
        <Button type="link" size="small" onClick={() => setDetailsOpen(true)}>查看完整数据</Button>
      </div>
      <Modal
        open={detailsOpen}
        title="本次用例初始化数据"
        footer={null}
        width={820}
        onCancel={() => setDetailsOpen(false)}
      >
        <AccountInitializationDetails initialState={state} />
      </Modal>
    </section>
  );
}

function CallPath({ steps }: { steps: ChainStep[] }) {
  return (
    <section className="agent-insight-block agent-call-path">
      <header><BranchesOutlined /><strong>调用路径</strong><span>{steps.length} 个节点</span></header>
      <div className="agent-call-path__rail">
        {steps.map((step, index) => (
          <div className={`agent-call-step agent-call-step--${step.category}`} key={step.id}>
            <span className={`agent-call-step__index${step.status === "failed" ? " is-failed" : ""}`}>{index + 1}</span>
            <div>
              <strong>{step.title}</strong>
              <small>{step.summary}</small>
            </div>
            <time>{formatDuration(step.duration_ms)}</time>
          </div>
        ))}
      </div>
    </section>
  );
}

function RecallFlow({ source }: { source: SourceSummary }) {
  const metrics = source.metrics;
  if (!metrics) return null;
  return (
    <div className="agent-source-card__recall">
      <span>{formatCount(metrics.searched)} → {formatCount(metrics.qualified)} → {formatCount(metrics.candidates)} → {formatCount(metrics.selected)}</span>
      <small>检索 → 过阈值 → 候选 → 采用{metrics.threshold != null ? ` · 阈值 ≥ ${metrics.threshold}` : ""}</small>
    </div>
  );
}

function RagSourceList({ title, sources }: { title: string; sources: RagSource[] }) {
  if (!sources.length) return <div className="agent-insight-empty">上游未提供该阶段的文献清单</div>;
  return (
    <section className="rag-audit-stage">
      <h4>{title}（{sources.length} 篇）</h4>
      {sources.map((source, sourceIndex) => (
        <details className="rag-audit-source" key={source.id || `${title}-${sourceIndex}`}>
          <summary>
            <strong>{sourceIndex + 1}. {source.title || "未命名文献"}</strong>
            <span>评分 {source.score ?? "—"} · {source.sourceTier || "未分级"}</span>
          </summary>
          <dl>
            <div><dt>文献 ID</dt><dd>{source.id || "—"}</dd></div>
            <div><dt>期刊 / 年份</dt><dd>{[source.journal, source.pubYear].filter(Boolean).join(" · ") || "—"}</dd></div>
            <div><dt>DOI / 链接</dt><dd>{source.doi || "—"}</dd></div>
            <div><dt>类型 / 证据等级</dt><dd>{[source.articleClass, source.confidenceLevel].filter(Boolean).join(" · ") || "—"}</dd></div>
          </dl>
          <h5>召回 Chunk（{source.chunks?.length || 0} 个）</h5>
          {(source.chunks || []).length ? source.chunks?.map((chunk, chunkIndex) => (
            <article className="rag-audit-chunk" key={`${source.id || sourceIndex}-${chunkIndex}`}>
              <div>#{chunk.sourceRank ?? chunkIndex + 1} · {chunk.sectionName || "未标注章节"} · 分数 {chunk.score ?? "—"}</div>
              <p>{chunk.content || "Chunk 内容为空"}</p>
              {chunk.raw ? (
                <details>
                  <summary>查看原始检索字段</summary>
                  <pre>{JSON.stringify(chunk.raw, null, 2)}</pre>
                </details>
              ) : null}
            </article>
          )) : <div className="agent-insight-empty">该文献未返回 Chunk 内容</div>}
        </details>
      ))}
    </section>
  );
}

function RagAuditButton({
  calls,
  loadCalls,
}: {
  calls: RagAuditCall[];
  loadCalls?: () => Promise<RagAuditCall[]>;
}) {
  const [open, setOpen] = useState(false);
  const [loadedCalls, setLoadedCalls] = useState<RagAuditCall[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const auditCalls = loadedCalls ?? calls;
  if (!auditCalls.length && !loadCalls) return null;
  const openAudit = async () => {
    setOpen(true);
    if (loadedCalls || calls.length || !loadCalls) return;
    setLoading(true);
    setLoadError(null);
    try {
      setLoadedCalls(await loadCalls());
    } catch {
      setLoadError("RAG 审计明细加载失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  };
  return (
    <>
      <Button type="link" size="small" onClick={() => void openAudit()}>查看 RAG 明细</Button>
      <Modal open={open} onCancel={() => setOpen(false)} footer={null} width={1080} title={`医学文献 RAG 调用明细（${auditCalls.length || "加载中"} 次）`}>
        <div className="rag-audit-modal">
          {loading ? <div className="agent-insight-empty">正在加载完整检索文献与 Chunk…</div> : null}
          {loadError ? <Alert type="error" showIcon message={loadError} /> : null}
          {!loading && !loadError && !auditCalls.length ? <div className="agent-insight-empty">该次调用未保存完整 RAG 审计快照</div> : null}
          {auditCalls.map((call, index) => (
            <section className="rag-audit-call" key={call.id || index}>
              <h3>第 {index + 1} 次检索 · {call.status === "available" ? "完整数据" : "数据截断"}</h3>
              {call.status !== "available" ? <Alert type="warning" showIcon message={call.unavailable_reason} /> : null}
              <dl>
                <div><dt>触发前 Query</dt><dd>{call.original_query || "上游未记录"}</dd></div>
                <div><dt>改写后检索 Query</dt><dd>{call.rewritten_query || "上游未记录"}</dd></div>
                <div><dt>检索模式</dt><dd>{call.mode || "—"}</dd></div>
              </dl>
              <div className="rag-audit-counts">检索 {formatCount(call.counts?.searched)} → 过阈值 {formatCount(call.counts?.qualified)} → 候选 {formatCount(call.counts?.candidates)} → 采用 {formatCount(call.counts?.selected)}{call.counts?.threshold != null ? ` · 阈值 ≥ ${call.counts.threshold}` : ""}</div>
              <p className="rag-audit-note">cx-agent 审计快照会保留完整 Top-K 原始命中；候选阶段未逐条标记时仅展示计数，不推测具体文献归属。</p>
              <RagSourceList title="全部检索文献" sources={call.all_sources || []} />
              <RagSourceList title="过阈值文献" sources={call.qualified_sources || []} />
              <RagSourceList title="候选文献" sources={call.candidate_sources || []} />
              <RagSourceList title="最终采用文献" sources={call.selected_sources || []} />
            </section>
          ))}
        </div>
      </Modal>
    </>
  );
}

function displaySources(
  sources: SourceSummary[],
  initialState?: CaseInitialState,
  responsePreference?: ReturnType<typeof responsePreferencePresentation>,
): SourceSummary[] {
  const profile = record(initialState?.user_profile);
  const profileDetails = Object.entries(profile)
    .filter(([, value]) => hasContent(value))
    .map(([key]) => profileLabels[key] || key.replace(/_/g, " "));
  const modules = accountInitializationModules(initialState);
  const moduleSourceKeys: Record<string, string> = {
    user_profile: "user_profile",
    timeline: "timeline",
    profile_memory: "profile_memory",
    response_preferences: "response_preferences",
    medical_documents: "medical_records",
    chat_history: "chat_history",
    scheduled_tasks: "scheduled_tasks",
    check_ins: "check_ins",
    undercurrent_tasks: "undercurrent_tasks",
  };
  const byKey = new Map(sources.map((source) => [source.key, source]));
  const sourceFromModule = (module: ReturnType<typeof accountInitializationModules>[number]): SourceSummary => {
    const key = moduleSourceKeys[module.key] || module.key;
    const existing = byKey.get(key);
    const details = module.entries.map((entry) => `${entry.label}：${entry.content}`);
    if (existing && existing.status !== "unused") {
      return { ...existing, label: module.label, details: [...details, ...existing.details] };
    }
    const preferenceInactive = module.key === "response_preferences" && responsePreference?.tone === "warning";
    const preferenceFailed = module.key === "response_preferences" && responsePreference?.tone === "error";
    return {
      key,
      label: module.label,
      status: preferenceInactive ? "inactive" : preferenceFailed ? "failed" : "injected",
      summary: module.key === "response_preferences" && responsePreference
        ? responsePreference.label
        : "已初始化到评测账号，本轮未调用对应工具",
      calls: 0,
      count: module.entries.length,
      details,
    };
  };
  const configured = modules.map(sourceFromModule);
  const configuredKeys = new Set(configured.map((source) => source.key));
  const remaining = sources
    .filter((source) => !configuredKeys.has(source.key))
    .filter((source) => source.key !== "chat_history" || source.status !== "unused");
  const metricsSource = byKey.get("medical_metrics");
  const documents = modules.find((module) => module.key === "medical_documents");
  if (documents && metricsSource?.status === "unused") {
    configured.splice(configured.findIndex((source) => source.key === "medical_records") + 1, 0, {
      ...metricsSource,
      label: "报告指标",
      status: "injected",
      summary: "已随病例夹初始化到评测账号，本轮未读取结构化指标",
      count: documents.entries.length,
      details: documents.entries.map((entry) => entry.label),
    });
    configuredKeys.add("medical_metrics");
  }
  return [
    ...(profileDetails.length && !configuredKeys.has("user_profile") ? [{
      key: "user_profile", label: "用户档案", status: "injected" as const,
      summary: "已注入本轮系统提示词，无需额外函数调用", calls: 0, count: profileDetails.length, details: profileDetails,
    }] : []),
    ...configured,
    ...remaining,
  ];
}

function assertionId(verdict: AssertionVerdict): string {
  return verdict.name.replace(/^assertion\./, "");
}

function assertionStatus(verdict: AssertionVerdict): "pass" | "fail" | "unavailable" {
  const status = String(verdict.details?.status || "").toLowerCase();
  if (status === "unavailable") return "unavailable";
  return verdict.passed === false || status === "fail" ? "fail" : "pass";
}

function assertionStatusLabel(verdict: AssertionVerdict): string {
  const status = assertionStatus(verdict);
  return status === "pass" ? "验收通过" : status === "fail" ? "验收未通过" : "暂无法校验";
}

function assertionSourceKeys(assertion: CaseEvaluationAssertion): string[] {
  if (assertion.type === "retrieval") {
    const name = String(assertion.name || "");
    return [{ medical_literature: "literature_rag" }[name] || name];
  }
  return [];
}

function assertionExpected(assertion: CaseEvaluationAssertion): string {
  if (assertion.type === "tool_call") {
    return `调用 ${assertion.name || "指定工具"} 至少 ${Number(assertion.min_count || 1)} 次`;
  }
  if (assertion.type === "retrieval") {
    return `${assertion.name || "指定数据来源"} 至少命中 ${Number(assertion.min_count || 1)} 次`;
  }
  if (assertion.type === "transcript") {
    return assertion.match_mode === "semantic"
      ? `回答应在语义上满足“${assertion.contains || "指定要求"}”`
      : `回答应包含“${assertion.contains || "指定内容"}”`;
  }
  return assertion.description || "满足性能限制";
}

function assertionActual(verdict: AssertionVerdict): string {
  const details = verdict.details || {};
  const type = String(details.type || "");
  if (type === "tool_call" || type === "retrieval") {
    const count = Number(details.count || 0);
    const minCount = Number(details.min_count || 1);
    return `命中 ${count}/${minCount} 次`;
  }
  if (type === "transcript") {
    return assertionStatus(verdict) === "pass" ? "已在检查范围内找到要求内容" : "在检查范围内未找到要求内容";
  }
  return verdict.reason || "未返回可展示的实际结果";
}

function assertionScoreImpact(
  assertion: CaseEvaluationAssertion,
  scoringStandard?: "cx_eight_dimension" | "model_comparison",
): string | null {
  if (assertion.type !== "transcript") return "未通过将导致本用例不合格，不扣八维分";
  const modelStandard = scoringStandard === "model_comparison";
  const dimensions = modelStandard ? assertion.model_comparison_dimensions : assertion.dimensions;
  const deduction = modelStandard ? assertion.model_comparison_deduction : assertion.deduction;
  if (dimensions?.length && Number(deduction || 0) > 0) {
    return `本次评分扣 ${deduction} 分 · ${agentDimensionLabels[dimensions[0]] || dimensions[0]}`;
  }
  return "未通过将导致本用例不合格，不扣八维分";
}

function AssertionResult({
  assertion,
  verdict,
  scoringStandard,
}: {
  assertion: CaseEvaluationAssertion;
  verdict?: AssertionVerdict;
  scoringStandard?: "cx_eight_dimension" | "model_comparison";
}) {
  if (!verdict) {
    return (
      <div className="agent-assertion-result is-unavailable">
        <div className="agent-assertion-result__head">
          <strong>{assertion.description || `${assertionTypeLabels[assertion.type || "tool_call"]}检查`}</strong>
          <span>未记录结果</span>
        </div>
        <p>预期：{assertionExpected(assertion)}</p>
        <small>该历史评测未保存断言结果；重新评测后会按实际链路重新校验。</small>
      </div>
    );
  }
  const status = assertionStatus(verdict);
  return (
    <div className={`agent-assertion-result is-${status}`}>
      <div className="agent-assertion-result__head">
        <strong>{assertion.description || `${assertionTypeLabels[assertion.type || "tool_call"]}检查`}</strong>
        <span>{assertionStatusLabel(verdict)}</span>
      </div>
      <p>预期：{assertionExpected(assertion)}</p>
      <p>实际：{assertionActual(verdict)}</p>
      {status !== "pass" && verdict.reason ? <small>{verdict.reason}</small> : null}
      {verdict.evidence?.length ? <small>链路证据：{verdict.evidence.join("；")}</small> : null}
      {status !== "pass" ? <em>{assertionScoreImpact(assertion, scoringStandard)}</em> : null}
    </div>
  );
}

function SourceGrid({
  sources,
  initialState,
  responsePreference,
  loadRagAudit,
  assertions = [],
  assertionVerdicts = [],
  scoringStandard,
}: {
  sources: SourceSummary[];
  initialState?: CaseInitialState;
  responsePreference?: ReturnType<typeof responsePreferencePresentation>;
  loadRagAudit?: () => Promise<RagAuditCall[]>;
  assertions?: CaseEvaluationAssertion[];
  assertionVerdicts?: AssertionVerdict[];
  scoringStandard?: "cx_eight_dimension" | "model_comparison";
}) {
  const visibleSources = displaySources(sources, initialState, responsePreference);
  const visibleAssertions = assertions.filter((assertion) => ["tool_call", "retrieval", "transcript"].includes(String(assertion.type || "")));
  const visibleIds = new Set(visibleAssertions.map((assertion) => String(assertion.id || "")));
  const visibleVerdicts = assertionVerdicts.filter((verdict) => visibleIds.has(assertionId(verdict)));
  const verdictById = new Map(visibleVerdicts.map((verdict) => [assertionId(verdict), verdict]));
  const matchedSourceAssertions = (sourceKey: string) => visibleAssertions.filter((assertion) => assertionSourceKeys(assertion).includes(sourceKey));
  const standaloneAssertions = visibleAssertions.filter((assertion) => assertion.type === "tool_call" || assertion.type === "transcript" || !assertionSourceKeys(assertion).length);
  const verified = visibleVerdicts.filter((verdict) => assertionStatus(verdict) === "pass").length;
  const failed = visibleVerdicts.filter((verdict) => assertionStatus(verdict) === "fail").length;
  const unavailable = visibleVerdicts.filter((verdict) => assertionStatus(verdict) === "unavailable").length;
  const summary = visibleVerdicts.length
    ? `${verified}/${visibleVerdicts.length} 通过${failed ? ` · ${failed} 项未满足` : ""}${unavailable ? ` · ${unavailable} 项待校验` : ""}`
    : visibleAssertions.length ? "等待运行结果" : "已初始化数据与实际工具读取均会展示";
  return (
    <section className="agent-insight-block agent-insight-block--wide">
      <header><DatabaseOutlined /><strong>信息来源与运行验收</strong><span>{summary}</span></header>
      <div className="agent-source-grid">
        {visibleSources.map((source) => {
          const sourceAssertions = matchedSourceAssertions(source.key);
          const hasFailedAssertion = sourceAssertions.some((assertion) => {
            const verdict = verdictById.get(String(assertion.id || ""));
            return verdict && assertionStatus(verdict) === "fail";
          });
          return (
            <article className={`agent-source-card is-${source.status}${hasFailedAssertion ? " has-assertion-fail" : ""}`} key={source.key}>
              <div className="agent-source-card__head">
                <strong>{source.label}</strong>
                <span>{sourceStatusLabels[source.status]}</span>
              </div>
              <p>{source.summary}</p>
              {hasContent(source.query) ? <div className="agent-source-card__query">查询：{inlineText(source.query)}</div> : null}
              <RecallFlow source={source} />
              {source.key === "literature_rag" && source.calls > 0 ? (
                <RagAuditButton calls={source.rag_audit || []} loadCalls={loadRagAudit} />
              ) : null}
              {source.details.length ? (
                <ul>{source.details.slice(0, 3).map((detail) => <li key={detail}>{detail}</li>)}</ul>
              ) : null}
              {sourceAssertions.map((assertion, index) => (
                <AssertionResult
                  key={`${assertion.id || source.key}-${index}`}
                  assertion={assertion}
                  verdict={verdictById.get(String(assertion.id || ""))}
                  scoringStandard={scoringStandard}
                />
              ))}
            </article>
          );
        })}
      </div>
      {standaloneAssertions.length ? (
        <div className="agent-assertion-extras">
          <strong>工具调用与回答验收</strong>
          <div className="agent-assertion-grid">
            {standaloneAssertions.map((assertion, index) => (
              <AssertionResult
                key={`${assertion.id || assertion.type || "assertion"}-${index}`}
                assertion={assertion}
                verdict={verdictById.get(String(assertion.id || ""))}
                scoringStandard={scoringStandard}
              />
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function Decisions({ risks, actions }: { risks: RiskSummary[]; actions: ActionSummary[] }) {
  return (
    <section className="agent-insight-block">
      <header><SafetyCertificateOutlined /><strong>医学判断与业务动作</strong></header>
      <div className="agent-decision-list">
        {risks.map((risk, index) => (
          <article className={`agent-decision is-${risk.status}`} key={`${risk.level}-${index}`}>
            <div><strong>风险 {risk.level}</strong><span>{risk.category}</span></div>
            <p>{risk.symptom || "未记录症状"}</p>
            <small>{risk.reason || "未记录判定依据"}</small>
          </article>
        ))}
        {actions.map((action, index) => (
          <article className={`agent-decision agent-decision--action is-${action.status}`} key={`${action.tool}-${index}`}>
            <div><strong>{action.label}</strong><span>{action.status === "success" ? "完成" : "失败"}</span></div>
            <p>{action.summary}</p>
          </article>
        ))}
        {!risks.length && !actions.length ? <div className="agent-insight-empty">本轮没有风险分级或业务动作</div> : null}
      </div>
    </section>
  );
}

function ChainQuality({ quality }: { quality: QualitySummary }) {
  const issues = [...quality.anomalies, ...quality.errors];
  return (
    <section className="agent-insight-block">
      <header><ThunderboltOutlined /><strong>链路质量</strong><span>{issues.length ? `${issues.length} 个问题` : "未见异常"}</span></header>
      <div className="agent-quality-facts">
        <div><span>模型</span><strong>{quality.models.join("、") || "—"}</strong></div>
        <div><span>Provider</span><strong>{quality.providers.join("、") || "—"}</strong></div>
        <div><span>工具成功</span><strong>{quality.tool_successes}/{quality.tool_calls}</strong></div>
        <div><span>上游重试</span><strong>{quality.retry_count}</strong></div>
      </div>
      {issues.length ? (
        <ul className="agent-quality-issues">{issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>
      ) : <div className="agent-quality-ok">调用、工具结果和最终回答协议均正常</div>}
    </section>
  );
}

export function AgentChainPanel({
  trace,
  syncing,
  onSync,
  caseInitialState,
  loadRagAudit,
  assertions,
  assertionVerdicts,
  scoringStandard,
}: {
  trace?: AgentChainTrace;
  syncing?: boolean;
  onSync: () => void;
  caseInitialState?: CaseInitialState;
  loadRagAudit?: () => Promise<RagAuditCall[]>;
  assertions?: CaseEvaluationAssertion[];
  assertionVerdicts?: AssertionVerdict[];
  scoringStandard?: "cx_eight_dimension" | "model_comparison";
}) {
  const identity = trace?.evaluation_identity || {};
  const chain = trace?.agent_chain || {};
  const traceIds = chain.trace_ids || trace?.langfuse_trace_ids || [];
  const nodes = chain.nodes || [];
  const summary = chain.summary;
  const candidateProfile = hasContent(identity.user_profile)
    ? record(identity.user_profile)
    : record(identity.profile_after_reset);
  const initialState = identity.initial_state || caseInitialState;
  const responsePreference = responsePreferencePresentation(identity, initialState);

  return (
    <DashPanel
      title="Agent 全链路"
      className="agent-chain-panel"
      extra={
        <Button size="small" icon={<ReloadOutlined />} loading={syncing} disabled={!traceIds.length} onClick={onSync}>
          重新同步
        </Button>
      }
    >
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <div className="agent-chain-identity">
          <span>登录账号 <strong>{loginAccount(identity)}</strong></span>
          <span>验证码 <strong>{identity.verification_code || "—"}</strong></span>
          <span>Cx Session <strong>{displayId(identity.cx_session_id)}</strong></span>
          <span>账号状态 <strong>{identity.reset_status === "success" ? "已清空" : "—"}</strong></span>
          {responsePreference ? (
            <span>
              回复偏好
              <strong className={`agent-runtime-status is-${responsePreference.tone}`}>
                {responsePreference.label}
              </strong>
            </span>
          ) : null}
        </div>

        {statusAlert(chain)}
        {!traceIds.length ? (
          <Alert type="info" showIcon message="该 Case 没有 cx-agent traceId" description="需要部署支持 evaluation_context SSE 的 cx-agent 版本后重新评测。" />
        ) : null}

        {summary ? (
          <>
            <div className="agent-insight-metrics">
              <Metric label="总耗时" value={formatDuration(summary.quality.total_duration_ms)} />
              <Metric label="模型调用" value={`${summary.quality.model_calls} 次`} hint={summary.quality.models.join("、") || undefined} />
              <Metric label="函数调用" value={`${summary.quality.tool_calls} 次`} hint={summary.quality.tool_failures ? `${summary.quality.tool_failures} 次失败` : "全部成功"} />
              <Metric label="累计 Token" value={formatCount(summary.quality.total_tokens)} hint={`输入 ${formatCount(summary.quality.input_tokens)} · 输出 ${formatCount(summary.quality.output_tokens)}`} />
              <Metric label="缓存命中" value={summary.quality.cache_hit_rate == null ? "—" : `${Math.round(summary.quality.cache_hit_rate * 100)}%`} hint={`${formatCount(summary.quality.cached_tokens)} tokens`} />
              <Metric label="链路状态" value={summary.quality.anomalies.length || summary.quality.errors.length ? "需关注" : "正常"} hint={summary.quality.retry_count ? `${summary.quality.retry_count} 次上游重试` : "无上游重试"} />
            </div>

            <div className="agent-insight-layout">
              <CallPath steps={summary.steps} />
              <ContextCard initialState={initialState} fallbackProfile={candidateProfile} />
              <SourceGrid
                sources={summary.sources}
                initialState={initialState}
                responsePreference={responsePreference}
                loadRagAudit={loadRagAudit}
                assertions={assertions}
                assertionVerdicts={assertionVerdicts}
                scoringStandard={scoringStandard}
              />
              <Decisions risks={summary.risks} actions={summary.actions} />
              <ChainQuality quality={summary.quality} />
            </div>

          </>
        ) : (
          <>
            {assertions?.length ? (
              <div className="agent-insight-layout">
                <SourceGrid
                  sources={[]}
                  initialState={initialState}
                  responsePreference={responsePreference}
                  loadRagAudit={loadRagAudit}
                  assertions={assertions}
                  assertionVerdicts={assertionVerdicts}
                  scoringStandard={scoringStandard}
                />
              </div>
            ) : null}
            {nodes.length ? (
              <Alert type="warning" showIcon message="链路摘要尚未生成" description="点击重新同步即可按最新规则提炼。" />
            ) : traceIds.length && chain.status === "synced" ? <Empty description="Trace 中暂无 observation" /> : null}
          </>
        )}
      </Space>
    </DashPanel>
  );
}
