import { Alert, Button, Descriptions, Empty, Space, Tag, Tree, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import type { DataNode } from "antd/es/tree";
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
  prompt?: Record<string, unknown>;
}

interface AgentChainSnapshot {
  status?: "synced" | "partial" | "failed" | "unconfigured";
  synced_at?: string;
  trace_ids?: string[];
  traces?: Array<{ trace_id?: string; trace_url?: string | null }>;
  nodes?: AgentChainNode[];
  error?: string | null;
}

interface EvaluationIdentity {
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

function jsonText(value: unknown): string {
  if (value === undefined || value === null || value === "") return "—";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function maskedId(value?: string): string {
  if (!value) return "—";
  return value.length > 12 ? `…${value.slice(-12)}` : value;
}

function usageTotal(usage?: Record<string, unknown>): string | null {
  if (!usage) return null;
  const value = usage.total ?? usage.total_tokens ?? usage.totalTokens;
  return typeof value === "number" ? `${value} tokens` : null;
}

function hasProfileContent(value: unknown): boolean {
  if (value === null || value === undefined || value === "") return false;
  if (Array.isArray(value)) return value.some(hasProfileContent);
  if (typeof value === "object") {
    return Object.values(value as Record<string, unknown>).some(hasProfileContent);
  }
  return true;
}

function NodeTitle({ node }: { node: AgentChainNode }) {
  const failed = node.level === "ERROR" || Boolean(node.status_message);
  return (
    <details onClick={(event) => event.stopPropagation()} style={{ padding: "4px 0" }}>
      <summary style={{ cursor: "pointer" }}>
        <Space size={8} wrap>
          <Typography.Text strong>{node.name || "未命名节点"}</Typography.Text>
          <Tag>{node.type || "SPAN"}</Tag>
          {node.duration_ms != null ? <Typography.Text type="secondary">{node.duration_ms} ms</Typography.Text> : null}
          {node.model ? <Typography.Text type="secondary">{node.model}</Typography.Text> : null}
          {usageTotal(node.usage) ? <Typography.Text type="secondary">{usageTotal(node.usage)}</Typography.Text> : null}
          {failed ? <Tag color="error">异常</Tag> : null}
        </Space>
      </summary>
      <Descriptions size="small" column={1} style={{ marginTop: 10 }}>
        <Descriptions.Item label="开始时间">{node.start_time || "—"}</Descriptions.Item>
        <Descriptions.Item label="错误">{node.status_message || "—"}</Descriptions.Item>
        <Descriptions.Item label="输入"><pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{jsonText(node.input)}</pre></Descriptions.Item>
        <Descriptions.Item label="输出"><pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{jsonText(node.output)}</pre></Descriptions.Item>
        <Descriptions.Item label="Metadata"><pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{jsonText(node.metadata)}</pre></Descriptions.Item>
      </Descriptions>
    </details>
  );
}

function buildTree(nodes: AgentChainNode[]): DataNode[] {
  const byId = new Map<string, DataNode>();
  const roots: DataNode[] = [];
  for (const node of nodes) {
    byId.set(node.id, { key: node.id, title: <NodeTitle node={node} />, children: [] });
  }
  for (const node of nodes) {
    const item = byId.get(node.id)!;
    const parent = node.parent_id ? byId.get(node.parent_id) : undefined;
    if (parent) (parent.children as DataNode[]).push(item);
    else roots.push(item);
  }
  return roots;
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
  const profile = identity.user_profile || identity.profile_after_reset || {};
  const nodesByTrace = new Map<string, AgentChainNode[]>();
  for (const node of nodes) {
    const key = node.trace_id || "unknown";
    nodesByTrace.set(key, [...(nodesByTrace.get(key) || []), node]);
  }

  return (
    <DashPanel
      title="Agent 全链路"
      extra={
        <Button size="small" icon={<ReloadOutlined />} loading={syncing} disabled={!traceIds.length} onClick={onSync}>
          重新同步
        </Button>
      }
    >
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Descriptions bordered size="small" column={{ xs: 1, md: 2, lg: 4 }}>
          <Descriptions.Item label="测试账号">{maskedId(identity.test_user_id)}</Descriptions.Item>
          <Descriptions.Item label="重置状态">{identity.reset_status === "success" ? <Tag color="success">已清空</Tag> : "—"}</Descriptions.Item>
          <Descriptions.Item label="重置时间">{identity.reset_at || "—"}</Descriptions.Item>
          <Descriptions.Item label="Cx Session">{maskedId(identity.cx_session_id)}</Descriptions.Item>
        </Descriptions>

        <div>
          <Typography.Text strong>请求前用户画像</Typography.Text>
          <pre style={{ marginTop: 8, padding: 12, background: "var(--surface-subtle)", whiteSpace: "pre-wrap" }}>
            {hasProfileContent(profile) ? jsonText(profile) : "空画像（本期基线评测）"}
          </pre>
        </div>

        {statusAlert(chain)}
        {!traceIds.length ? (
          <Alert type="info" showIcon message="该 Case 没有 cx-agent traceId" description="需要部署支持 evaluation_context SSE 的 cx-agent 版本后重新评测。" />
        ) : null}

        {chain.traces?.length ? (
          <Space wrap>
            {chain.traces.map((item, index) => (
              <a key={item.trace_id || index} href={item.trace_url || undefined} target="_blank" rel="noreferrer">
                Trace {index + 1} · {maskedId(item.trace_id)}
              </a>
            ))}
          </Space>
        ) : trace?.langfuse_trace_url ? (
          <a href={trace.langfuse_trace_url} target="_blank" rel="noreferrer">在 Langfuse 查看</a>
        ) : null}

        {nodes.length ? (
          [...nodesByTrace.entries()].map(([traceId, traceNodes], index) => (
            <div key={traceId}>
              <Typography.Text strong>第 {index + 1} 轮 Trace · {maskedId(traceId)}</Typography.Text>
              <Tree
                style={{ marginTop: 8 }}
                selectable={false}
                defaultExpandAll
                showLine
                treeData={buildTree(traceNodes)}
              />
            </div>
          ))
        ) : traceIds.length && chain.status === "synced" ? <Empty description="Trace 中暂无 observation" /> : null}
      </Space>
    </DashPanel>
  );
}
