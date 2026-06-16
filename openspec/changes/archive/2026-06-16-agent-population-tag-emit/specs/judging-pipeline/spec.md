## ADDED Requirements

### Requirement: RuleJudge 必须在 must_have 失败时按 profile emit 受控 FailureTag

当用例 `score_profile` 为 `population` 且 `rule.must_have` 判 FAIL 时，verdict MUST emit `FailureTag.POPULATION_BLIND`（而非 `INQUIRY_INCOMPLETE`）。其余 profile 保持 `INQUIRY_INCOMPLETE`。

#### Scenario: population 题 must_have 失败

- **WHEN** `score_profile=population` 且 must_have 未命中
- **THEN** `rule.must_have.failure_tags` MUST 含 `population_blind`
