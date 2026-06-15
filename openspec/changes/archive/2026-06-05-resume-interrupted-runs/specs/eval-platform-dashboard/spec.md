# eval-platform-dashboard Specification (delta)

## ADDED Requirements

### Requirement: 用例列表指南匹配率带命中计数

用例列表的「指南匹配率」列 MUST 在百分比之外带出具体命中计数，以 `X%（matched/total）` 形式展示，其中 matched/total 为该用例带指南锚点得分点的命中数与总数。计数 MUST 由服务端从已落 `detail_json` 派生（`CaseRowOut.guideline_matched` / `guideline_total`），无需数据库迁移、对历史 run 同样生效。当用例无带指南锚点的得分点时，列 MUST 显示「无锚点」而非 `0/0`。

#### Scenario: 列表带计数

- **WHEN** 某用例有 6 个带指南锚点的得分点且全部命中
- **THEN** 列表该行指南匹配率 MUST 显示为 `100%（6/6）`

#### Scenario: 无指南锚点

- **WHEN** 某用例无带指南锚点的得分点
- **THEN** 列表该行 MUST 显示「无锚点」而非 `0/0` 或 `0%`
