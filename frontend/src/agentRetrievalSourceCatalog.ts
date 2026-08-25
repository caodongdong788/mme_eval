import capabilities from "../../shared/agent_capabilities.json";

export type AgentRetrievalSourceCatalogItem = {
  name: string;
  title: string;
  description: string;
  category: string;
};

/** MME 从 cx-agent 调用链摘要中可确定验证的 6 类数据来源。 */
export const AGENT_RETRIEVAL_SOURCE_CATALOG = capabilities.retrieval_sources.map(
  ({ name, title, description, category }) => ({ name, title, description, category }),
) as AgentRetrievalSourceCatalogItem[];

export const AGENT_RETRIEVAL_SOURCE_BY_NAME = new Map(
  AGENT_RETRIEVAL_SOURCE_CATALOG.map((source) => [source.name, source]),
);

/** 历史 YAML 曾使用过的来源名称；界面与评测继续兼容，但新配置统一使用标准名称。 */
export const AGENT_RETRIEVAL_SOURCE_ALIASES = Object.fromEntries(
  capabilities.retrieval_sources.flatMap((source) =>
    source.aliases.map((alias) => [alias, source.name]),
  ),
) as Record<string, string>;

export function resolveAgentRetrievalSource(name: string): AgentRetrievalSourceCatalogItem | undefined {
  const canonicalName = AGENT_RETRIEVAL_SOURCE_ALIASES[name] || name;
  return AGENT_RETRIEVAL_SOURCE_BY_NAME.get(canonicalName);
}
