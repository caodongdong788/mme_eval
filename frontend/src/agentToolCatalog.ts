import capabilities from "../../shared/agent_capabilities.json";

export type AgentToolCatalogItem = {
  name: string;
  title: string;
  description: string;
  category: string;
};

export const AGENT_TOOL_CATALOG = capabilities.tools as AgentToolCatalogItem[];

export const AGENT_TOOL_BY_NAME = new Map(AGENT_TOOL_CATALOG.map((tool) => [tool.name, tool]));
