import {
  Alert,
  Button,
  Empty,
  Space,
} from "antd";
import {
  BranchesOutlined,
  DatabaseOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { DashPanel } from "./DashPanel";

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
  status: "unused" | "listed" | "read" | "queried" | "hit" | "miss" | "failed";
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
  status?: "synced" | "partial" | "failed" | "unconfigured";
  synced_at?: string;
  trace_ids?: string[];
  traces?: Array<{ trace_id?: string; trace_url?: string | null }>;
  nodes?: AgentChainNode[];
  summary?: AgentChainSummary;
  error?: string | null;
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
}

export interface AgentChainTrace {
  langfuse_trace_url?: string | null;
  langfuse_trace_ids?: string[];
  evaluation_identity?: EvaluationIdentity;
  agent_chain?: AgentChainSnapshot;
}

const sourceStatusLabels: Record<SourceSummary["status"], string> = {
  unused: "未调用",
  listed: "仅查看目录",
  read: "已读取",
  queried: "已查询",
  hit: "已命中",
  miss: "未命中",
  failed: "调用失败",
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
  const type = chain.status === "partial" ? "warning" : "info";
  const label = {
    partial: "部分 Trace 已同步",
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

function ProfileCard({ profile }: { profile: Record<string, unknown> }) {
  const entries = Object.entries(profile).filter(([, value]) => hasContent(value)).slice(0, 10);
  if (!entries.length) return null;
  return (
    <section className="agent-insight-block agent-profile-card">
      <header><UserOutlined /><strong>用户画像</strong><span>{entries.length} 项</span></header>
      <dl>
        {entries.map(([key, value]) => (
          <div key={key}>
            <dt>{profileLabels[key] || key.replace(/_/g, " ")}</dt>
            <dd>{inlineText(value)}</dd>
          </div>
        ))}
      </dl>
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

function SourceGrid({ sources }: { sources: SourceSummary[] }) {
  return (
    <section className="agent-insight-block agent-insight-block--wide">
      <header><DatabaseOutlined /><strong>信息来源</strong><span>是否真正读取，一眼可见</span></header>
      <div className="agent-source-grid">
        {sources.map((source) => (
          <article className={`agent-source-card is-${source.status}`} key={source.key}>
            <div className="agent-source-card__head">
              <strong>{source.label}</strong>
              <span>{sourceStatusLabels[source.status]}</span>
            </div>
            <p>{source.summary}</p>
            {hasContent(source.query) ? <div className="agent-source-card__query">查询：{inlineText(source.query)}</div> : null}
            <RecallFlow source={source} />
            {source.details.length ? (
              <ul>{source.details.slice(0, 3).map((detail) => <li key={detail}>{detail}</li>)}</ul>
            ) : null}
          </article>
        ))}
      </div>
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
}: {
  trace?: AgentChainTrace;
  syncing?: boolean;
  onSync: () => void;
}) {
  const identity = trace?.evaluation_identity || {};
  const chain = trace?.agent_chain || {};
  const traceIds = chain.trace_ids || trace?.langfuse_trace_ids || [];
  const nodes = chain.nodes || [];
  const summary = chain.summary;
  const candidateProfile = hasContent(identity.user_profile)
    ? record(identity.user_profile)
    : record(identity.profile_after_reset);

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
        </div>

        {statusAlert(chain)}
        {!traceIds.length ? (
          <Alert type="info" showIcon message="该 Case 没有 cx-agent traceId" description="需要部署支持 evaluation_context SSE 的 cx-agent 版本后重新评测。" />
        ) : null}

        {nodes.length && summary ? (
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
              <ProfileCard profile={candidateProfile} />
              <SourceGrid sources={summary.sources} />
              <Decisions risks={summary.risks} actions={summary.actions} />
              <ChainQuality quality={summary.quality} />
            </div>

          </>
        ) : nodes.length ? (
          <Alert type="warning" showIcon message="链路摘要尚未生成" description="点击重新同步即可按最新规则提炼。" />
        ) : traceIds.length && chain.status === "synced" ? <Empty description="Trace 中暂无 observation" /> : null}
      </Space>
    </DashPanel>
  );
}
