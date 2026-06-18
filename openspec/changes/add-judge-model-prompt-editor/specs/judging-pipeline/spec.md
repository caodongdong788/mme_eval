## ADDED Requirements

### Requirement: LLMJudge 可配置 prompt_template

`LLMJudge` MUST 接受可选 `prompt_template` 字符串。当非空时，判分 MUST 使用该模板（`.format(conversation=..., rubric_text=..., tool_context=...)`）；当为空时 MUST 沿用内置默认模板。`prompt_template` MUST 纳入 `LLMJudge.fingerprint()`。

#### Scenario: 自定义模板生效

- **WHEN** `judges.llm.prompt_template` 为非空字符串
- **THEN** LLM judge 调用 MUST 使用该模板而非内置默认

#### Scenario: 空模板回退

- **WHEN** `prompt_template` 为空
- **THEN** LLM judge MUST 使用内置 `_PROMPT_TEMPLATE`，行为与变更前一致
