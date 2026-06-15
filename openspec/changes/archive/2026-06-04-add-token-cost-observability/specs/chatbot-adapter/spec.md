## ADDED Requirements

### Requirement: Adapter 在 LLM 返回 usage 时必须保留可归一化的 token 用量

当被测后端在响应中返回 token usage 时，adapter 产出的 `ChatResponse.raw` MUST 包含可被 runner 归一化的 token 用量字段（OpenAI 风格 `usage.prompt_tokens / completion_tokens / total_tokens`）。该字段 MUST 仅作观测数据保留，MUST NOT 影响 `reply` 内容或判分。后端未返回 usage 时 adapter MUST NOT 伪造数值（留空即可）。

#### Scenario: openai_compat 保留 usage

- **WHEN** openai_compat adapter 收到含 `usage` 的成功响应
- **THEN** `ChatResponse.raw["usage"]` MUST 含 `prompt_tokens / completion_tokens / total_tokens`

#### Scenario: 后端无 usage 时不伪造

- **WHEN** 后端响应未携带 usage
- **THEN** `ChatResponse.raw` 中 usage MUST 为空（缺省 `{}`），MUST NOT 出现编造的 token 数
