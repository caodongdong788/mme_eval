# Proposal: F3.2 大页面子组件拆分 + 快照测试

## Why

`RunDashboardPage`（~618 行）与 `CaseDetailPage`（~605 行）承担过多 UI 编排与展示逻辑，维护成本高。
`platform-quality-refactor` 的 F3.2 项当时刻意搁置为独立变更；现以「行为 100% 不变」为前提完成拆分，
并配套 vitest 快照测试锁定 UI 结构。

## What Changes

- 接入 `vitest` + `@testing-library/react` + `jsdom`，新增 `npm run test`。
- 从 `CaseDetailPage` 抽出：`ConversationThread`、`CaseDetailSummaryCard`、`CaseDimensionScoresCard`、
  `JudgeVerdictTable`、`ScoringPointsTable`、`HumanReviewCard`；`judgeLabel` / `guidelineMatch` 等迁至
  `utils/caseJudging.ts`。
- 从 `RunDashboardPage` 抽出：`FilterToolbar`、`RunDashboardHeader`、`RunCaseResultsCard`、`RunDiffCard`。
- 页面瘦身为编排层（CaseDetail ~324 行、RunDashboard ~427 行）。
- 新增 8 个测试文件（7 组 snapshot + `caseJudging` 单元测试），测试 setup 补 `matchMedia` mock。

## Impact

- Affected specs: 无（纯前端结构重构，不改 API / 判分 / 交互语义）。
- Affected code: `frontend/src/pages/RunDashboardPage.tsx`、`CaseDetailPage.tsx`、新增 `components/*`、
  `utils/caseJudging.ts`、`vitest.config.ts`、`src/test/setup.ts`、`package.json`。
- 行为：筛选、对话展示、路由、sessionStorage 筛选项记忆等与拆分前一致。
