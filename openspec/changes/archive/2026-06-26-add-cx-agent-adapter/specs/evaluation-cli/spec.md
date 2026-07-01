# 评测命令行入口 Delta

## ADDED Requirements

### Requirement: 默认配置必须声明 cx-agent 被测对象

仓库默认 `config.yaml` MUST 显式声明当前被测对象为 `cx_agent`，并只保留其必要子块；临时 `openai_compat` / `http` 被测 bot 配置不得继续作为默认被测对象残留。

#### Scenario: 默认配置声明 cx-agent

- **WHEN** 用户加载仓库默认 `config.yaml`
- **THEN** `config.adapter.type` MUST 为 `cx_agent`，且必须包含 `adapter.cx_agent` 子块。
