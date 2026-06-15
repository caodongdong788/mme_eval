## ADDED Requirements

### Requirement: diff_runs 必须输出性能（会话延迟）对比块

`diff_runs` MUST 在既有 regression / improvement diff 输出之外，基于两份 report 的 `latency_summary` 额外输出一段「性能变化」Markdown 块，使版本间的会话延迟变化可被直观对比。该块 MUST 至少呈现 平均 / 中位 / P90 / 最大 四项延迟的 当前值、上版本值与差值（Δ，单位 ms），并 MUST 标注延迟"仅记录、不计分、不否决"，不得影响通过率 / regression / improvement 的判定与排序。

当当前 report 无 `latency_summary` 数据时，`diff_runs` MUST NOT 渲染该块（避免空表）。当上版本 report 缺 `latency_summary`（历史报告）时，`diff_runs` MUST 输出友好提示说明无法对比性能，且 MUST NOT 抛错。

#### Scenario: 两版均有延迟数据

- **当** 当前与上版本 report 的 `latency_summary` 均非空
- **那么** diff Markdown 末尾 MUST 含「性能变化」块，列出 平均/中位/P90/最大 的 当前/上版/Δ，并标注"仅记录、不计分"

#### Scenario: 上版本缺延迟数据

- **当** 上版本 report 没有 `latency_summary` 字段（历史报告）
- **那么** `diff_runs` MUST 输出 ℹ️ 提示"上版本未记录延迟数据，无法对比性能"，且不抛错

#### Scenario: 当前无延迟数据

- **当** 当前 report 的 `latency_summary` 为空（全部 run 失败）
- **那么** `diff_runs` MUST NOT 渲染性能对比块
