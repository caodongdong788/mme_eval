## ADDED Requirements

### Requirement: 报告必须呈现得分点逐点命中与指南匹配率

markdown 报告 MUST 为声明了得分点的用例呈现"得分点逐点命中明细"：每个得分点 MUST 显示其 `criterion`、分值、命中状态（命中/未命中），并 MUST 标注负分点。报告 MUST 单独呈现"指南匹配率"切片，且 MUST 与 HardGate 通过率分开展示、明确标注该指标本期"仅度量、未设否决"，避免被误读为合格线。无得分点的用例 MUST NOT 出现空的得分点段。

#### Scenario: 含得分点用例展示逐点明细

- **WHEN** 一条用例有正分与负分得分点，部分命中
- **THEN** 报告 MUST 列出每个得分点的描述、分值、命中状态，并标注哪些是负分（惩罚）点

#### Scenario: 指南匹配率独立展示且标注非否决

- **WHEN** 报告聚合存在带指南锚点的得分点
- **THEN** 报告 MUST 输出指南匹配率数值，并 MUST 附文案说明其"仅度量、未参与合格判定"

#### Scenario: 无得分点用例不显示空段

- **WHEN** 一批用例均无 `scoring_points`
- **THEN** 报告 MUST NOT 渲染任何得分点明细或指南匹配率段
