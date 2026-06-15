# case-schema-and-loader (delta)

## ADDED Requirements

### Requirement: ExpectedBehavior 必须支持 output_checks 结构化断言

`ExpectedBehavior` MUST 支持可选字段 `output_checks: list[OutputCheck]`（默认空列表）。每个
`OutputCheck` MUST 含受控枚举 `kind`、参数字典 `params` 与可选 `note`。loader 加载校验
MUST 接受合法 `output_checks` 并对未知 `kind` 报错；缺省（不写该字段）MUST 与历史用例完全等价。

#### Scenario: 加载带 output_checks 的用例

- **WHEN** 用例 YAML 在 `expected_behavior.output_checks` 下声明一条 `kind=max_chars`、`params={max: 200}`
- **THEN** loader MUST 成功加载并保留该断言

#### Scenario: 未知 kind 被拒

- **WHEN** 用例声明一个不在受控枚举内的 `kind`
- **THEN** loader/schema 校验 MUST 报错

#### Scenario: 缺省字段向后兼容

- **WHEN** 用例未声明 `output_checks`
- **THEN** 该用例 MUST 与引入本字段前行为完全一致
