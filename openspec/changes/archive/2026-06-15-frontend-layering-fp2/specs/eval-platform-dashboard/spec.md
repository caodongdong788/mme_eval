## MODIFIED Requirements

### Requirement: 前端页面组件化与快照测试

CRUD 编辑弹窗的 open/editId/form/saving 状态 MUST 复用 `hooks/useEditModal`（或等价抽象），避免在多个 page hook 内重复样板。
`RunOverviewTab` 的 KPI、观测指标与图表区 MUST 拆为独立 `components/`，数据派生逻辑 MAY 收敛至 `useRunOverviewData`。
用例详情 YAML 试判预览 UI MUST 由独立组件（如 `CasePreviewRejudgePanel`）渲染；纯重构 MUST NOT 改变试判、图表与 CRUD 交互行为。

#### Scenario: 看板概览由子块组装

- **WHEN** 用户打开 run 看板「概览」Tab
- **THEN** KPI、延迟/Token、分层级/模块/标签图表 MUST 由独立 components 渲染
- **AND** 展示数值与拆分前一致

#### Scenario: 试判预览组件可快照回归

- **WHEN** 维护者修改 `CasePreviewRejudgePanel`
- **THEN** `npm run test` MUST 能通过对应 snapshot 测试
