# Tasks

## 1. 测试基建
- [x] 1.1 接入 vitest + @testing-library/react + jsdom，`npm run test` / `test:watch`
- [x] 1.2 `src/test/setup.ts`：matchMedia mock + jest-dom

## 2. 抽组件（CaseDetailPage）
- [x] 2.1 `utils/caseJudging.ts`（judgeLabel / scoringPointWeight / guidelineMatch + CaseVerdict 类型）
- [x] 2.2 `ConversationThread`、`CaseDetailSummaryCard`、`CaseDimensionScoresCard`
- [x] 2.3 `JudgeVerdictTable`、`ScoringPointsTable`、`HumanReviewCard`

## 3. 抽组件（RunDashboardPage）
- [x] 3.1 `FilterToolbar`
- [x] 3.2 `RunDashboardHeader`、`RunCaseResultsCard`、`RunDiffCard`

## 4. 快照 / 单元测试
- [x] 4.1 7 组组件 snapshot + caseJudging 单元测试（17 passed）

## 5. 验证与归档
- [x] 5.1 `typecheck` / `lint`（0 errors）/ `build` 全绿
- [x] 5.2 `graphify update .`
- [x] 5.3 `openspec validate --strict` → `openspec archive`
