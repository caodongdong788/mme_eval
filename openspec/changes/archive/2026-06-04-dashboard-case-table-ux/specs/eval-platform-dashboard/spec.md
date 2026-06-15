# eval-platform-dashboard Specification (delta)

## MODIFIED Requirements

### Requirement: 看板审核队列与裁定界面

看板 SHALL 暴露人工审核能力：「用例结果」区 MUST 提供「待审 N」徽标与「仅看待审」筛选（数据取自
review-queue / review-stats），并 MUST 展示一张统计卡（人审通过率 / 分歧率 / 待审·已审计数）。
「仅看待审」筛选开启时 MUST 只展示在审核队列内且**尚未有人审结果**的用例（已裁定用例移出待审视图）。
「用例结果」区还 MUST 提供「人审结果」筛选（同意 / 推翻 / 未审），可与其它筛选叠加，并按 run 维度
随其它筛选条件一并记忆。
用例详情页 MUST 提供裁定面板：选择 `同意机器` / `推翻机器`、可填建议修正与备注并提交，提交后
MUST 展示该用例已有裁定列表。选「推翻机器」时面板 MUST 提供「去改判据(YAML)」入口跳转到看板的
YAML 改判据另存流程（复用 derive-yaml）。看板统计 MUST NOT 改动 medeval 报告内核。

#### Scenario: 从详情页提交裁定

- **WHEN** 用户在用例详情页选择同意/推翻并提交
- **THEN** 前端 MUST 调用 annotate API 落库，并刷新展示该用例的裁定列表

#### Scenario: 看板呈现待审与统计

- **WHEN** 用户打开含待审用例的 run 看板
- **THEN** 看板 MUST 显示待审计数徽标，并可筛选只看待审用例，统计卡 MUST 显示人审通过率/分歧率

#### Scenario: 仅看待审排除已审用例

- **WHEN** 用户开启「仅看待审」且队列中部分用例已有人审结果
- **THEN** 列表 MUST 只显示队列内尚未裁定的用例，已裁定用例 MUST NOT 出现

#### Scenario: 按人审结果筛选

- **WHEN** 用户选择「人审结果=推翻」
- **THEN** 列表 MUST 只显示最新裁定为推翻的用例

## ADDED Requirements

### Requirement: 用例结果表列展示

看板"用例结果"表列标题 MUST 使用「场景描述」（用例链接列）与「类别」以避免语义混淆，且各列宽度
MUST 自适应内容（避免表头拥挤换行）。

#### Scenario: 列标题与自适应宽度

- **WHEN** 用户查看用例结果表
- **THEN** 链接列标题 MUST 为「场景描述」、分类列 MUST 为「类别」，且列宽 MUST 按内容自适应
