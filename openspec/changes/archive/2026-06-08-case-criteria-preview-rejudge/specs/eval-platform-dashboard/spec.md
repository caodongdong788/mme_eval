## ADDED Requirements

### Requirement: 用例明细就地编辑判据并单条试判预览

用例明细页 SHALL 支持就地（不跳离当前页）编辑当前用例判据并预览重判效果。HITL 裁定面板选「推翻机器」
时，「去改判据(YAML)」入口 MUST 就地打开判据编辑器（复用看板同一编辑器组件），并 MUST 以**仅当前
`sample_id` 这一条用例**的完整 YAML 预填（前端经带 `sample_id` 的 cases-yaml 取得）。

编辑器内 MUST 提供「试判此用例（预览）」动作：前端 MUST 调用 preview-rejudge 端点，展示新 verdict /
四维分 / 综合分 / 上线判定及与当前值的 diff。该预览 MUST 明确标注为「仅预览，不修改当前 run」，且
MUST NOT 触发任何落库或重判。用户满意后 MUST 可复用既有「覆盖当前 benchmark」/「另存为新 benchmark」
将判据落回 benchmark；界面 MUST 提示「覆盖仅更新判据源、不改当前 run 已存分，要得到修正结果需另行重判」。

#### Scenario: 推翻后就地编辑单条判据

- **WHEN** 用户在用例明细 HITL 面板选「推翻机器」并点「去改判据(YAML)」
- **THEN** 前端 MUST 就地打开判据编辑器并仅预填当前用例 YAML，MUST NOT 跳转到看板列表页

#### Scenario: 单条试判预览不改当前 run

- **WHEN** 用户在编辑器内修改判据后点「试判此用例（预览）」
- **THEN** 前端 MUST 调用 preview-rejudge 并展示新判定与 diff，且 MUST 标注「仅预览、不改当前 run」，
  MUST NOT 触发落库或重判

### Requirement: 判据编辑器展示当前 benchmark 名称

判据编辑器（看板入口与用例明细入口共用）MUST 在界面显著位置展示**当前正在编辑/覆盖的 benchmark 名称**
（形如 `#<id>「<名称>」`），使用户在「覆盖当前 benchmark」前能确认覆盖对象，避免误覆盖。

#### Scenario: 编辑判据时可见 benchmark 名称

- **WHEN** 用户打开判据编辑器
- **THEN** 编辑器 MUST 展示当前 run 关联 benchmark 的 `#id「名称」`

## MODIFIED Requirements

### Requirement: 看板审核队列与裁定界面

看板 SHALL 暴露人工审核能力：「用例结果」区 MUST 提供「待审 N」徽标与「仅看待审」筛选（数据取自
review-queue / review-stats），并 MUST 展示一张统计卡（人审通过率 / 分歧率 / 待审·已审计数）。
「仅看待审」筛选开启时 MUST 只展示在审核队列内且**尚未有人审结果**的用例（已裁定用例移出待审视图）。
「用例结果」区还 MUST 提供「人审结果」筛选（同意 / 推翻 / 未审），可与其它筛选叠加，并按 run 维度
随其它筛选条件一并记忆。
用例详情页 MUST 提供裁定面板：选择 `同意机器` / `推翻机器`、可填建议修正与备注并提交，提交后
MUST 展示该用例已有裁定列表。选「推翻机器」时面板 MUST 提供「去改判据(YAML)」入口，该入口 MUST
就地打开判据编辑器并仅预填当前用例 YAML（详见「用例明细就地编辑判据并单条试判预览」需求），MUST NOT
再跳转到看板列表页。看板统计 MUST NOT 改动 medeval 报告内核。

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

#### Scenario: 推翻入口就地打开编辑器

- **WHEN** 用户在详情页选「推翻机器」并点「去改判据(YAML)」
- **THEN** 前端 MUST 就地打开判据编辑器（仅预填当前用例 YAML），MUST NOT 跳转到看板列表页
