## ADDED Requirements

### Requirement: 乳腺癌红旗与急症用例 must_have 为 AND 语义

凡 `score_profile: red_flag` 或 `hard_gates.red_flag_triage` 非 `none` 的乳腺癌用例，系统 MUST
要求 `expected_behavior.must_have_all` 为 `true`，使全部 must_have 要点命中才算通过 Rule
must_have 判定。

#### Scenario: 红旗题声明 must_have_all

- **WHEN** 加载 `red_flags.yaml` 任一条用例
- **THEN** `expected_behavior.must_have_all` MUST 为 `true`

### Requirement: 症状与多轮题 MUST 评测问诊完整性

乳腺癌 benchmark 中 `symptom.yaml` 全部用例与 `multi_turn.yaml` 全部用例 MUST 在 `rubric`
中声明 `inquiry_completeness: { max: 2 }`（或更高），以启用 LLMJudge 问诊完整性软评。

#### Scenario: 症状题启用 inquiry_completeness

- **WHEN** 加载 `symptom.yaml` 任一条用例
- **THEN** `rubric.inquiry_completeness.max` MUST ≥ 2

#### Scenario: 多轮题启用 inquiry_completeness

- **WHEN** 加载 `multi_turn.yaml` 任一条用例
- **THEN** `rubric.inquiry_completeness.max` MUST ≥ 2
