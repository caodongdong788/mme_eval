# Proposal: Frontend Layering F-P0（Pairwise 域分层）

## Why

前端审查显示 Pairwise 两页仍内联业务逻辑（`PairwisePage` ~366 行、`PairwiseDetailPage` ~407 行），`PairwiseConversationCol` 在组件内直接请求 API，与 `frontend-workflow.mdc`「pages 只做编排、组件无副作用取数」不一致。

## What Changes

- 新增 `hooks/usePairwisePage.ts`：发起对比、预检、历史轮询、备注/删除
- 新增 `hooks/useCaseMessages.ts`：`getCaseDetail` 取对话，供展开行使用
- 抽 `PairwiseVerdictTags`（结论/置信 Tag + 表头 Hint）
- 抽 `PairwiseCreateCard`、`PairwiseHistoryTable`、`PairwiseDetailRunningCard`、`PairwiseDetailSummaryCard`、`PairwiseCaseTable`、`PairwiseExpandedRow`
- `PairwiseConversationCol` 改为纯展示（`messages` props）
- 配套 vitest 快照/单测；**零行为变更**

## Non-Goals

- 不推广 `useAsyncData` 到其他页面（F-P1）
- 不改 API、路由、交互文案

## Risks

- 拆分后 props 穿透 → 用域内子组件收敛，页面仅组合 hook + 组件
