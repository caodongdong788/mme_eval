# Proposal: Frontend Layering F-P2（CRUD 复用 + 大块 UI 拆分）

## Why

F-P1 后 CRUD hooks（JudgeModels/Benchmarks）仍重复 modal/form 样板；`CaseDetailPage` 试判区块与 `RunOverviewTab`（250 行）仍偏大。

## What Changes

- 新增 `useEditModal`：统一创建/编辑弹窗 state
- 抽 `CasePreviewRejudgePanel`；`CaseDetailPage` 仅组合
- 拆 `RunOverviewTab` → `RunOverviewKpiGrid` / `RunOverviewMetricsPanel` / `RunOverviewCharts` + `useRunOverviewData`
- 配套 vitest 快照；**零行为变更**

## Non-Goals

- 不改 API、路由、图表数据口径
