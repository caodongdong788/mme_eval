# judging-pipeline (delta)

## ADDED Requirements

### Requirement: RuleJudge 必须执行用例声明的结构化 Output Check

`RuleJudge` MUST 对用例 `expected_behavior.output_checks` 逐条执行**确定性**结构化校验（零 LLM
调用），每条产出一个 `rule.output_check{i}` verdict。支持的 `kind` 至少含 `max_chars`、
`min_chars`、`must_contain`、`forbid_regex`、`json_valid`、`required_fields`。失败的 verdict
MUST 附 `FailureTag.CONSTRAINT_VIOLATION`。当 `output_checks` 为空时，RuleJudge MUST NOT 产出任何
`rule.output_check*` verdict（对存量用例零行为变化）。

Output Check 校验逻辑 MUST 纳入 `RuleJudge.fingerprint()`。Output Check MUST NOT 写
`hard_gate.*` / `gate_passed`；其失败仅经报告层功能模块扣分影响 `release_passed`。

#### Scenario: 长度上限超限判失败

- **WHEN** 用例声明 `max_chars=50` 且 bot 回复长度为 80
- **THEN** 对应 `rule.output_check{i}` verdict MUST `passed=false` 且含 `CONSTRAINT_VIOLATION`

#### Scenario: 必含结构段命中通过

- **WHEN** 用例声明 `must_contain` 某正则且 bot 回复命中
- **THEN** 对应 verdict MUST `passed=true`

#### Scenario: JSON 字段齐全校验

- **WHEN** 用例声明 `required_fields=["title","summary"]` 且 bot 回复缺 `summary`
- **THEN** 对应 verdict MUST `passed=false`

#### Scenario: 无声明零行为变化

- **WHEN** 用例未声明 `output_checks`
- **THEN** RuleJudge MUST NOT 产出任何 `rule.output_check*` verdict

### Requirement: 功能模块必须按失败的 Output Check 扣分

报告层功能模块 MUST 对每条失败的 `rule.output_check*` verdict 从功能满分起扣一个
`function_deduction`（与 must_not_have 命中同口径），并记录可读扣分原因。该扣分 MUST 进入
`release_passed` 判定，且 MUST NOT 影响 `hard_gate_passed` / `gate_passed`。

#### Scenario: 失败 Output Check 计入功能扣分

- **WHEN** 一条 output_check 失败、`function_deduction=0.10`
- **THEN** 该用例功能模块得分 MUST 比无该失败时少 0.10，并在扣分原因中体现
