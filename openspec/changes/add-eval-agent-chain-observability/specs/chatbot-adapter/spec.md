## ADDED Requirements

### Requirement: cx-agent 评测账号必须按 Case 隔离

CxAgentAdapter MUST 在每个 Case/run 首轮前领取并重置一个专用测试账号，同一 Case 多轮 MUST 复用同一账号，不同并发 Case MUST NOT 共用账号，Case 结束后 MUST 释放租约。

#### Scenario: 两个 Case 并发执行

- **WHEN** Runner 并发执行两个 Case
- **THEN** 两个 Case 使用不同 test user，且各自在首轮前完成重置

### Requirement: Adapter 必须保留 cx-agent Trace 关联信息

Adapter MUST 解析 cx-agent `evaluation_context` SSE 事件，将 `traceId`、测试用户、重置证据和画像快照保留到运行 Trace；多轮产生的多个 traceId MUST 全部保留。

#### Scenario: 多轮 Case

- **WHEN** 同一 Case 执行两轮用户输入且 cx-agent 返回两个 traceId
- **THEN** Case 的 `langfuse_trace_ids` 按首次出现顺序包含两个 id
