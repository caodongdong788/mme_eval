## MODIFIED Requirements

### Requirement: 报告必须呈现延迟统计且标注仅记录不计分

markdown 报告 MUST 能呈现 `RunReport.latency_summary` 的延迟统计（至少 平均、中位、P90、最大，单位 ms），并标注延迟"仅记录、不计分、不否决"，与通过率、软分等评分类信息分区呈现。

为避免与「与上版本对比」中的「性能变化」块重复，独立的"性能（仅记录）"段 MUST 仅在该次报告**未呈现**版本对比性能块时作为兜底渲染（即无 diff、关闭 diff、或上版本无延迟数据）；当报告已含「性能变化」块时 MUST NOT 再渲染独立段。当既无版本对比性能块、又无任何成功 run 的延迟数据时，延迟呈现 MUST 显示为不适用（N/A）而非渲染空表。

#### Scenario: 无对比时兜底展示延迟统计

- **WHEN** 一次评测有延迟数据但未生成版本对比性能块（如首次评测或关闭 diff）
- **THEN** 报告 MUST 输出独立"性能（仅记录）"段（avg/median/p90/max + "仅记录、不计分"标注）

#### Scenario: 已有对比性能块时不重复

- **WHEN** 「与上版本对比」已含「性能变化」块
- **THEN** 报告 MUST NOT 再渲染底部独立"性能（仅记录）"段

#### Scenario: 无延迟数据时不渲染空表

- **WHEN** 全部 run 均失败、无可用延迟数据，且无版本对比性能块
- **THEN** 延迟呈现 MUST 显示为不适用（N/A），MUST NOT 渲染空表格

### Requirement: diff_runs 必须输出性能（会话延迟）对比块

`diff_runs` MUST 在既有 regression / improvement diff 输出之外，基于两份 report 的 `latency_summary` 额外输出一段「性能变化」Markdown 块，使版本间的会话延迟变化可被直观对比。该块 MUST 至少呈现 平均 / 中位 / P90 / 最大 四项延迟的 当前值、上版本值与变化（差值，单位 ms，第四列列名为"变化"，以 ↑ 变慢 / ↓ 变快 标注方向），并 MUST 标注延迟"仅记录、不计分、不否决"，不得影响通过率 / regression / improvement 的判定与排序。

当当前 report 无 `latency_summary` 数据时，`diff_runs` MUST NOT 渲染该块（避免空表）。当上版本 report 缺 `latency_summary`（历史报告）时，`diff_runs` MUST 输出友好提示说明无法对比性能，且 MUST NOT 抛错。

#### Scenario: 两版均有延迟数据

- **当** 当前与上版本 report 的 `latency_summary` 均非空
- **那么** diff Markdown 末尾 MUST 含「性能变化」块，列出 平均/中位/P90/最大 的 当前/上版/变化（第四列表头为"变化"），并标注"仅记录、不计分"

#### Scenario: 上版本缺延迟数据

- **当** 上版本 report 没有 `latency_summary` 字段（历史报告）
- **那么** `diff_runs` MUST 输出 ℹ️ 提示"上版本未记录延迟数据，无法对比性能"，且不抛错

#### Scenario: 当前无延迟数据

- **当** 当前 report 的 `latency_summary` 为空（全部 run 失败）
- **那么** `diff_runs` MUST NOT 渲染性能对比块
