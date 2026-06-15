# eval-platform-service (delta)

## ADDED Requirements

### Requirement: Pairwise 逐用例人工校准

系统 MUST 允许对已完成的 Pairwise 对比逐用例进行人工校准，覆写有效结论、三维度归属与理由；
校准后 `confidence_kind` MUST 为 `human`。机器原判字段 MUST 保留且 MUST NOT 被校准覆盖。
`DELETE` 同用例校准 MUST 恢复为机器有效值并重算汇总。

校准或恢复后，`PairwiseComparison.summary` MUST 按全部用例的**有效值**立即重算（胜/平/负、
低置信细分、维度胜率、overall_winner、回退/改善清单），列表与详情 MUST 回显重算结果。

#### Scenario: 人工改结论后汇总联动

- **WHEN** 某用例机器判 `tie` 被人工校准为 `winner=B`
- **THEN** 该对比的 `summary.b_wins` MUST 递增、`summary.ties` MUST 递减，且 `overall_winner`
  等统计 MUST 与有效值一致

#### Scenario: 恢复机器判定

- **WHEN** 对已校准用例执行恢复
- **THEN** 有效值 MUST 回到机器原判，summary MUST 按机器口径重算
