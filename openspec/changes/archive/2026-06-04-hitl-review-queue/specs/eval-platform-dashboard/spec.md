# eval-platform-dashboard Specification (delta)

## ADDED Requirements

### Requirement: 看板审核队列与裁定界面

看板 SHALL 暴露人工审核能力：「用例结果」区 MUST 提供「待审 N」徽标与「仅看待审」筛选（数据取自
review-queue / review-stats），并 MUST 展示一张统计卡（人审通过率 / 分歧率 / 待审·已审计数）。
用例详情页 MUST 提供裁定面板：选择 `同意机器` / `推翻机器`、可填建议修正与备注并提交，提交后
MUST 展示该用例已有裁定列表。选「推翻机器」时面板 MUST 提供「去改判据(YAML)」入口跳转到看板的
YAML 改判据另存流程（复用 derive-yaml）。看板统计 MUST NOT 改动 medeval 报告内核。

#### Scenario: 从详情页提交裁定

- **WHEN** 用户在用例详情页选择同意/推翻并提交
- **THEN** 前端 MUST 调用 annotate API 落库，并刷新展示该用例的裁定列表

#### Scenario: 看板呈现待审与统计

- **WHEN** 用户打开含待审用例的 run 看板
- **THEN** 看板 MUST 显示待审计数徽标，并可筛选只看待审用例，统计卡 MUST 显示人审通过率/分歧率
