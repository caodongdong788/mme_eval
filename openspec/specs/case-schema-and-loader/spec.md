# 用例 Schema 与加载器（case-schema-and-loader）

## Purpose

定义"医疗 chatbot 评测用例"的可机读结构（YAML），以及从磁盘加载、校验、过滤这些用例的规则。这是整套评测框架的输入侧契约：所有 Adapter / Runner / Judge / Reporter 都直接消费此处生成的 `TestCase` 对象，因此 schema 的稳定性与校验的严格性决定了下游模块的可靠性。

设计原则：

- **Single source of truth**：`TestCase` 是评测的最小不可变单元；运行期产物（trace、verdict、report）禁止修改它。
- **失败优先 (fail fast)**：任何字段缺失、类型错配或 `sample_id` 重复都必须在加载阶段抛错，不允许带病进入 Runner。
- **可审计**：每个用例自带 `source` / `notes`，便于回溯用例本身的演进。
- **医疗保守语义**：默认 `no_prescription=True`，红旗分诊默认 `none`（不要"默认就触发急救"，避免假阳性）。
## Requirements
### Requirement: 系统必须以 Pydantic 模型定义所有用例字段

系统 MUST 为每一条 YAML 用例提供严格的 Pydantic v2 Schema，覆盖 sample_id、scenario / sub_scenario、level、**score_profile**、source、turns、expected_behavior、hard_gates、rubric、failure_tags_candidates、notes 等字段。Schema MUST NOT 声明 `population` 或 `difficulty` 字段；历史 YAML 中的对应 key MUST 被静默忽略。`score_profile` MUST 为受控枚举 `default` / `red_flag` / `adversarial` / `knowledge` / `rehab`，默认 `default`；若 YAML 误写为列表 MUST 只取第一个元素。内置 benchmark 的 YAML MUST 将 `score_profile` 写在 `level` 之后。Schema MUST NOT 再声明 `tags` 字段；历史 YAML 中的 `tags` key MUST 导致校验失败（非 silent ignore）。

#### 场景:score_profile 决定评分 profile

- **当** 用例 `score_profile: knowledge`
- **那么** `resolve_profile()` MUST 返回 config 中 `profiles.knowledge` 的权重与 pass_rule

#### 场景:加载非法 tags 必须失败

- **当** YAML 仍含 `tags: [...]`
- **那么** Pydantic 校验 MUST 失败

#### Scenario: 历史 population/difficulty 被忽略

- **WHEN** YAML 含 `population: adult` 或 `difficulty: hard`
- **THEN** loader MUST 成功加载且 `TestCase` MUST NOT 暴露上述属性

#### Scenario: 内置 benchmark 元数据顺序

- **WHEN** 加载 `cases/breast_cancer/*.yaml`
- **THEN** 每条用例 MUST 不含 `population` / `difficulty` 键，且 `score_profile` 位于 `level` 之后

### Requirement: TestCase 必须支持 HealthBench 式 scoring_points 得分点

`TestCase` MUST 新增字段 `scoring_points: list[ScoringPoint]`，默认 `Field(default_factory=list)`（向后兼容历史用例与 `report.json`）。`ScoringPoint` MUST 是一个 Pydantic model，包含字段：

- `criterion: str`（必填）：人类可读的得分点描述，作为 grader 判定命中与否的依据。
- `points: int`（必填）：分值，**MAY 为负**；正分表示"应满足的要点"，负分表示"出现即惩罚的内容"。
- `guideline: str = ""`：可选指南/证据锚点（如指南名 + 条目），用于派生指南匹配率；为空表示该点不计入指南匹配率。
- `critical: bool = False`：是否关键点（本期仅作标注与展示，不触发否决）。

loader MUST 能加载并通过 schema 校验该结构；`points == 0` MUST 被校验拒绝（无意义的零分点）。

#### Scenario: 历史用例无 scoring_points 字段

- **WHEN** 加载一条未声明 `scoring_points` 的旧用例 YAML
- **THEN** `TestCase.scoring_points` MUST 默认为 `[]`，加载与校验 MUST 不报错

#### Scenario: 合法的正负分得分点被加载

- **WHEN** 一条用例声明 `scoring_points: [{criterion: "应建议短期随访复查", points: 2, guideline: "中国抗癌协会乳腺癌指南/BI-RADS 3"}, {criterion: "替患者断定良恶性", points: -3}]`
- **THEN** loader MUST 成功构造两个 `ScoringPoint`，其中第二个 `points == -3`、`guideline == ""`、`critical == False`

#### Scenario: 零分得分点被拒绝

- **WHEN** 某用例声明一个 `points: 0` 的得分点
- **THEN** schema 校验 MUST 失败并指出该得分点分值非法

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

