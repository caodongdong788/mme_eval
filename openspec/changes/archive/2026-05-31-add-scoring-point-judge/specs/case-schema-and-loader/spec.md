## ADDED Requirements

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
