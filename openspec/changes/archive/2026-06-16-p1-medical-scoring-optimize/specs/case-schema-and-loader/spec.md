## MODIFIED Requirements

### Requirement: 系统必须以 Pydantic 模型定义所有用例字段

`score_profile` MUST 扩展为受控枚举 `default` / `red_flag` / `adversarial` / `knowledge` / `rehab` / `population` / `agent`。config 中 `pass_rule.gates` 的值 MUST 为字面量 `full` 或 (0,1] 区间浮点比例；拼写错误（如 `fulll`）MUST 在校验阶段拒绝。

#### Scenario:population profile 合法

- **WHEN** YAML 声明 `score_profile: population`
- **THEN** loader MUST 成功解析且保留枚举值 `population`

#### Scenario:gate 拼写错误被拒绝

- **WHEN** config `pass_rule.gates.safety: fulll`
- **THEN** `parse_config` MUST 抛出 `ConfigError`
