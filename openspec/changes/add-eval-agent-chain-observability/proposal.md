# Proposal: add-eval-agent-chain-observability

## Why

SIT cx-agent 评测当前共用固定测试用户，只隔离 `sessionId`，用户级画像与长期记忆可能跨 Case 串扰；平台也只保存一个 Langfuse 外链，无法在 Case 明细中直接审阅 Agent、模型和工具调用链。

## What Changes

- cx-agent 测试路由提供三个隔离评测账号的租约、全量重置、释放接口。
- MME cx-agent adapter 在每个 Case/run 开始时领取并重置账号，结束时释放。
- cx-agent SSE 返回评测身份快照与每轮 `traceId`。
- MME 从 Langfuse Public API 拉取 observations，归一化并固化到 Case trace。
- Case 明细展示账号重置、用户画像、Trace 列表和完整调用树。

## Scope

- `medeval/adapter/`、`medeval/runner/`、`medeval/models.py`
- `server/services/`、正常评测 job
- `frontend/src/components/`、Case 明细页
- cx-agent `packages/backend/src/routes/test.ts`

## Success

- 并发 Case 不共享账号；每个 Case 开始前账号为空白状态。
- 多轮 Case 的每一轮 cx-agent Trace 均能关联到同一 Case。
- Langfuse 暂时不可用时评测仍正常完成，并在明细中显示同步状态。
- Case 明细可查看用户画像与 Agent/Generation/Tool 父子调用关系。
