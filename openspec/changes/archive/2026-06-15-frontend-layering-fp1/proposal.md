# Proposal: Frontend Layering F-P1（推广 hooks + useAsyncData）

## Why

F-P0 完成 Pairwise 域分层后，其余 CRUD/列表页仍内联 `useState + useEffect + api.*`；`useAsyncData` 未被使用。F-P1 将取数与副作用收敛至 hooks，页面仅编排。

## What Changes

- 修复 `useAsyncData` effect cleanup（竞态取消）
- 新增 `useRunsList`、`useBenchmarksPage`、`useJudgeModelsPage`、`useTrendsPage`、`useReleaseThresholdsPage`、`useLaunchPage`、`useCaseDetail`
- 瘦身对应 `pages/*`；**零行为变更**
- 配套 vitest 单测

## Non-Goals

- 不拆 Modal/Table 子组件（除非页面仍 >300 行）
- 不改 API、路由
