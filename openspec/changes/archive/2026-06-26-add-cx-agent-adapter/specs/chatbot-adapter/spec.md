# Chatbot 适配器 Delta

## ADDED Requirements

### Requirement: 系统必须提供 cx-agent SSE Adapter

系统 MUST 提供 `CxAgentAdapter`，用于调用 cx-agent 本地测试路由 `/api/test/chat/send`。该 adapter 必须通过 `@register_adapter("cx_agent", config_key="cx_agent")` 注册，配置校验与工厂分发必须继续复用 adapter 注册表作为单一真值源。

Adapter MUST 使用 `X-Test-Token` 请求头传递测试 token，token 必须从配置声明的环境变量读取，或从本地调试字段读取；缺失 token 时必须在构造期 fail-fast。请求体必须发送最新 user turn 的 `content`，并在已建立映射时发送 cx-agent 返回的 `sessionId` 续聊。

Adapter MUST 解析 cx-agent SSE：`session` 事件保存真实 `sessionId`，`text_delta` 事件按顺序拼接 assistant 回复，`message_end` 事件作为正常结束信号，`error` 事件必须转换为 `ChatResponse.error`。底层网络异常或非法 SSE 必须转换为 `ChatResponse.error`，禁止裸异常向上抛。

#### Scenario: 单轮 SSE 回复被拼接

- **WHEN** cx-agent 返回 `session`、两个 `text_delta` 和 `message_end`
- **THEN** `ChatResponse.reply` 必须等于两个文本片段顺序拼接后的字符串，`raw.cx_session_id` 必须记录 cx-agent session。

#### Scenario: 多轮复用 cx-agent session

- **WHEN** 同一个 `ChatRequest.session_id` 连续调用两次
- **THEN** 第二次请求体必须携带第一次 `session` 事件返回的 cx-agent `sessionId`。

#### Scenario: cx-agent error 事件转为 adapter error

- **WHEN** SSE 中出现 `event: error`
- **THEN** Adapter 必须返回 `ChatResponse.error`，并保留已解析 raw events 便于排查。

### Requirement: cx-agent Adapter 必须拒绝预置非用户历史

cx-agent 测试路由自身在本地 DB 中维护历史。`CxAgentAdapter` MUST 仅发送当前最新 user turn，禁止把 Runner 传入的完整历史重新拼成用户消息发送。若首轮请求包含预置 `system` 或 `assistant` 历史，Adapter MUST fail-fast 返回 `ChatResponse.error`，避免把评测上下文污染为用户输入。

#### Scenario: 预置 system turn 被拒绝

- **WHEN** `ChatRequest.messages` 在最新 user turn 之前包含 `system` 消息且当前 mme session 尚未建立 cx-agent session
- **THEN** Adapter 必须返回非空 `ChatResponse.error`，且不得请求 cx-agent。
