## ADDED Requirements

### Requirement: 看板必须展示成本/Token 卡片

run 看板 MUST 新增"成本 / Token（仅观测）"卡片，展示 `token_summary` 的总 token、平均每 run token，以及配置单价时的 cost。该卡片 MUST 明确为观测信息（不计分），与延迟卡片同等地位呈现。当本次 run 无 token 数据时，卡片 MUST 显示友好的"无 token 数据"提示而非空白或报错。

#### Scenario: 有 token 数据展示卡片

- **WHEN** 打开一个含 token 数据的 run 看板
- **THEN** MUST 显示总 token / 平均每 run token（配置单价时含 cost）

#### Scenario: 无数据友好提示

- **WHEN** run 无 token 数据
- **THEN** 卡片 MUST 显示"本次评测无 token 数据"提示
