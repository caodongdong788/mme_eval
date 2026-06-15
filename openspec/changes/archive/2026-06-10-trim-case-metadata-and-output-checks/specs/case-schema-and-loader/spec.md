## MODIFIED Requirements

### Requirement: 系统必须以 Pydantic 模型定义所有用例字段

系统 MUST 为每一条 YAML 用例提供严格的 Pydantic v2 Schema，覆盖 sample_id、scenario / sub_scenario、level、**score_profile**、source、turns、expected_behavior、hard_gates、rubric、failure_tags_candidates、notes 等字段。`population` / `difficulty` MAY 保留 schema 默认值以兼容旧上传，但内置 benchmark YAML MUST NOT 写入这两项。`score_profile` MUST 为受控枚举 `default` / `red_flag` / `adversarial` / `knowledge` / `rehab`，默认 `default`；若 YAML 误写为列表 MUST 只取第一个元素。内置 benchmark 的 YAML MUST 将 `score_profile` 写在 `level` 之后。Schema MUST NOT 再声明 `tags` 字段；历史 YAML 中的 `tags` key MUST 导致校验失败（非 silent ignore）。

#### 场景:score_profile 决定评分 profile

- **当** 用例 `score_profile: knowledge`
- **那么** `resolve_profile()` MUST 返回 config 中 `profiles.knowledge` 的权重与 pass_rule

#### 场景:加载非法 tags 必须失败

- **当** YAML 仍含 `tags: [...]`
- **那么** Pydantic 校验 MUST 失败

#### Scenario: 内置 benchmark 元数据顺序

- **WHEN** 加载 `cases/breast_cancer/*.yaml`
- **THEN** 每条用例 MUST 不含 `population` / `difficulty` 键，且 `score_profile` 位于 `level` 之后

### Requirement: ExpectedBehavior 必须支持 output_checks 结构化断言

`ExpectedBehavior` MUST 支持可选字段 `output_checks: list[OutputCheck]`（默认空列表）。每个
`OutputCheck` MUST 含受控枚举 `kind`、参数字典 `params` 与可选 `note`。loader 加载校验
MUST 接受合法 `output_checks` 并对未知 `kind` 报错；缺省（不写该字段）MUST 与历史用例完全等价。内置 benchmark 的每条用例 MUST 在 `expected_behavior` 下显式写出 `output_checks` 键（可为空列表 `[]`）。

#### Scenario: 加载带 output_checks 的用例

- **WHEN** 用例 YAML 在 `expected_behavior.output_checks` 下声明一条 `kind=max_chars`、`params={max: 200}`
- **THEN** loader MUST 成功加载并保留该断言

#### Scenario: 未知 kind 被拒

- **WHEN** 用例声明一个不在受控枚举内的 `kind`
- **THEN** loader/schema 校验 MUST 报错

#### Scenario: 缺省字段向后兼容

- **WHEN** 用例未声明 `output_checks`
- **THEN** 该用例 MUST 与引入本字段前行为完全一致

#### Scenario: 内置 benchmark 显式空 output_checks

- **WHEN** 加载内置 `cases/breast_cancer/*.yaml`
- **THEN** 每条用例 MUST 含 `expected_behavior.output_checks` 键
