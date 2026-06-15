# eval-platform-dashboard Specification (delta)

## ADDED Requirements

### Requirement: 用例结果表人审结果列

看板"用例结果"表 SHALL 新增「人审结果」列：对有人审裁定的用例渲染「同意」/「推翻」标签，
鼠标悬浮 MUST 展示该裁定的建议（suggestion）与备注（comment）；无裁定的用例 MUST 显示占位（如 -）。

#### Scenario: 列表展示人审结论并悬浮详情

- **WHEN** 某用例已被人工裁定为推翻并填写了建议
- **THEN** 该行「人审结果」列 MUST 显示「推翻」标签，悬浮 MUST 显示其建议与备注
