# judging-pipeline (delta)

## ADDED Requirements

### Requirement: Pairwise 有效值与 confidence_kind

Pairwise 逐用例对外展示与汇总 MUST 使用有效值：若 `human_calibrated=true` 则取 `human_*` 字段，
否则取机器字段。`confidence_kind` MUST 为受控枚举 `high | order | safety | human`（人工校准
为 `human`；机器低置信 MUST 细分为 `order`（顺序敏感）或 `safety`（安全存疑））。

#### Scenario: 未校准用例 confidence_kind

- **WHEN** 用例 `confidence=high`
- **THEN** `confidence_kind` MUST 为 `high`

- **WHEN** 用例 `confidence=low` 且 `swap_consistent=false`
- **THEN** `confidence_kind` MUST 为 `order`
