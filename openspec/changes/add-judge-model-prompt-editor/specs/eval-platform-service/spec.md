## ADDED Requirements

### Requirement: 判分模型 prompt_template 持久化

`judge_model_config` MUST 持久化可选字段 `prompt_template`（TEXT，可空）。`GET/POST/PATCH /api/judge-models` MUST 读写该字段；空值 MUST 表示沿用内核默认 judge prompt。

#### Scenario: 保存自定义 prompt

- **WHEN** 用户创建或更新判分模型并提交非空 `prompt_template`
- **THEN** 列表与详情接口 MUST 返回该字段，且发起评测选用该模型时 MUST 注入运行期 judge 覆盖

### Requirement: Prompt 质检接口

平台 MUST 提供 `POST /api/judge-models/optimize-prompt`，请求体 `{ "prompt": string }`，响应 `{ "optimized_prompt": string }`。该接口 MUST 使用服务器 `config.yaml` 中 `judges.llm` 的连接配置调用 LLM 优化 prompt，MUST NOT 使用用户表单中选定的判分模型凭据。LLM 未配置或调用失败时 MUST 返回非 2xx 与可读 `detail`。

#### Scenario: 优化成功

- **WHEN** 客户端提交非空 prompt 且服务端 judge LLM 可用
- **THEN** 响应 MUST 含 `optimized_prompt` 且 MUST 保留 `{conversation}`、`{rubric_text}`、`{tool_context}` 占位符
