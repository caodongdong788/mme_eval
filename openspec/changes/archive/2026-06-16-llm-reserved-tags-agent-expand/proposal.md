# Proposal: llm-reserved-tags-agent-expand

## Why

预留 `over_refusal` / `tool_misuse` 标签尚未由 Judge emit；agent 专题仅 4 题，第五维 inquiry 统计不稳。

## What Changes

1. **LLMJudge** 在 rubric 打分 JSON 中解析 `flags`，对非红旗题 emit `over_refusal`、对工具误用 emit `tool_misuse`（纯归因，不改 gate/score）。
2. **`cases/breast_cancer/agent.yaml`** 扩至 **8** 道多轮 agent 题（+4）。
3. 文档与测试计数 88→92。
