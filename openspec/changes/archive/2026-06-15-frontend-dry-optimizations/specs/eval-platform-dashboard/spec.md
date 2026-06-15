## MODIFIED Requirements

### Requirement: 前端页面组件化与快照测试

CRUD 编辑弹窗的 open/editId/form/saving 状态 MUST 复用 `hooks/useEditModal`（或等价抽象），避免在多个 page hook 内重复样板。
配置类标签映射（失败标签、Judge verdict 中文）MUST 复用 `hooks/useConfigLabelMap`（或等价抽象），全应用每种映射只拉取一次。
Run / 用例详情打开 YAML 判据编辑器的加载逻辑 MUST 复用 `hooks/useYamlEditorState`（或等价抽象）。
Pairwise 页初始数据拉取 SHOULD 复用 `hooks/useAsyncData`；展开行 A/B 对话 MUST 经 `hooks/usePairwiseExpandedMessages`（或等价）并行拉取并模块级缓存，避免重复 `getCaseDetail`。
`RunOverviewTab` 的 KPI、观测指标与图表区 MUST 拆为独立 `components/`，数据派生逻辑 MAY 收敛至 `useRunOverviewData`。
用例详情 YAML 试判预览 UI MUST 由独立组件（如 `CasePreviewRejudgePanel`）渲染；纯重构 MUST NOT 改变试判、图表与 CRUD 交互行为。

#### Scenario: 看板概览由子块组装

- **WHEN** 用户打开 run 看板「概览」Tab
- **THEN** KPI、延迟/Token、分层级/模块/标签图表 MUST 由独立 components 渲染
- **AND** 展示数值与拆分前一致

#### Scenario: Pairwise 展开行复用对话缓存

- **WHEN** 用户在 Pairwise 对比详情中展开同一用例行两次
- **THEN** 第二次展开 MUST NOT 对同一 run+sample 重复发起 `getCaseDetail`（除非显式失效缓存）

#### Scenario: 试判预览组件可快照回归

- **WHEN** 维护者修改 `CasePreviewRejudgePanel`
- **THEN** `npm run test` MUST 能通过对应 snapshot 测试
