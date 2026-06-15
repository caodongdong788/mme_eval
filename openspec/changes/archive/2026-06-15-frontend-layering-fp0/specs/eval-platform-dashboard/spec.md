## MODIFIED Requirements

### Requirement: 前端页面组件化与快照测试

前端 `pages/` 层 SHALL 仅承担路由参数、数据获取与页面级 state 编排；可复用的展示与交互块
MUST 沉淀至 `frontend/src/components/`（或 `frontend/src/hooks/` / `utils/` 纯函数），禁止在单页文件内堆积数百行 UI。
Pairwise 列表页与详情页 MUST 将 API 调用与副作用收敛至 `hooks/usePairwisePage`、`hooks/usePairwiseDetail`、`hooks/useCaseMessages`；
`PairwiseConversationCol` MUST 为纯展示组件（由父级或 `PairwiseExpandedRow` 注入 `messages`）。
从 `RunDashboardPage` / `CaseDetailPage` / **Pairwise 页面** 抽出的核心块 MUST 配套 vitest + `@testing-library/react` 快照或单元测试，以锁定拆分前后
UI 结构与关键文案一致；纯重构 MUST NOT 改变筛选、对话展示、路由回退或 sessionStorage 筛选项记忆等行为。

#### Scenario: Pairwise 页由 hook 与子组件组装且行为不变

- **WHEN** 用户打开 Pairwise 列表或对比详情页
- **THEN** 发起对比、历史轮询、预检、备注/删除及详情筛选 MUST 由 hooks 承载
- **AND** 结论/置信 Tag、对话列、历史表格 MUST 由独立 components 渲染
- **AND** 交互与拆分前一致（含展开行加载对话、返回用例明细深链）

#### Scenario: 抽出组件具备快照回归

- **WHEN** 维护者修改 `PairwiseVerdictTags` 或纯展示 `PairwiseConversationCol`
- **THEN** `npm run test` MUST 能通过对应 snapshot / 单元测试，否则视为非预期 UI 漂移
