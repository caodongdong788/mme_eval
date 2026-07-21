# Design: eval account isolation and agent chain observability

## Account lifecycle

cx-agent 在非生产测试路由内维护三个专用 UUID。MME 以自身 `session_id` 作为 lease id：首次聊天前领取账号，cx-agent 原子锁定、清空账号并重建空白用户；同一 Case 多轮复用租约；Case 完成后释放。旧调用未携带租约时继续使用历史固定测试用户，保持兼容。

## Trace correlation

每次 cx-agent HTTP turn 仍是一条独立 Langfuse trace。测试 SSE 新增 `evaluation_context`，携带 `traceId`、`sessionId`、测试用户、评测元数据与请求前画像快照。MME 将多轮 `traceId` 聚合到 `ConversationTrace.langfuse_trace_ids`。

## Snapshot ingestion

正常评测完成、落库前，MME 通过服务端 Basic Auth 查询 Langfuse observations。优先使用 v2 observations API，旧自托管实例不支持 v2或 v2 尚未完成写入时自动回退 v1（兼容 cx-agent 当前 Langfuse JS SDK 5.3 的 v2 延迟）。响应归一化为稳定的 flat node schema，保留 parent id 供前端构树。同步采用有限重试并 fail-soft；凭据不进入报告。

## UI

Case 明细新增“Agent 全链路”区域：身份与重置证据、画像快照、Trace 摘要、按父子关系展示的 Agent/Generation/Tool 节点，以及输入、输出、模型、Token、耗时和错误。

## Privacy

不展示测试账号手机号或任何凭据。Langfuse 原始输入输出沿用 cx-agent 的采集与脱敏策略；MME 不记录 Authorization header。
