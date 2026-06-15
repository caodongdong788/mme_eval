# eval-platform-dashboard（delta）

## ADDED Requirements

### Requirement: 前端页面组件化与快照测试

前端 `pages/` 层 SHALL 仅承担路由参数、数据获取与页面级 state 编排；可复用的展示与交互块
MUST 沉淀至 `frontend/src/components/`（或 `utils/` 纯函数），禁止在单页文件内堆积数百行 UI。
从 `RunDashboardPage` / `CaseDetailPage` 抽出的核心块（含 `ConversationThread`、`FilterToolbar` 及
关联判定/复核卡片）MUST 配套 vitest + `@testing-library/react` 快照或单元测试，以锁定拆分前后
UI 结构与关键文案一致；纯重构 MUST NOT 改变筛选、对话展示、路由回退或 sessionStorage 筛选项记忆等行为。

#### Scenario: 看板与用例明细由子组件组装且行为不变

- **WHEN** 用户打开 run 看板的用例明细 Tab 或用例详情页
- **THEN** 筛选工具栏、对话流水、Judge 判定表等 MUST 由独立 components 渲染
- **AND** 筛选、下钻、返回、人工复核等交互 MUST 与拆分前一致

#### Scenario: 抽出组件具备快照回归

- **WHEN** 维护者修改 `ConversationThread` 或 `FilterToolbar` 等已抽出组件
- **THEN** `npm run test` MUST 能通过对应 snapshot / 单元测试，否则视为非预期 UI 漂移
