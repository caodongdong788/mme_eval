## Why

报告里「性能（仅记录）」段只展示**本次** run 的会话延迟（样本/平均/中位/P90/最大），而「与上版本对比」段只比通过率、分层级、regression/improvement——**唯独不比性能**。

用户做版本对比时无法直观看到"这一版比上一版快了还是慢了"，必须人工翻两份报告的延迟表手算差值。`latency_summary` 本就随 `RunReport` 写进 `report.json`，`diff_runs` 也已同时持有 cur / prev 两份 json，差的只是把延迟纳入对比输出。

## What Changes

- `medeval/reporter/diff.py` 新增纯函数 `_latency_diff(cur, prev) -> str`：对比两份 report 的 `latency_summary`，输出「性能变化」Markdown 块（平均 / 中位 / P90 / 最大，列出 当前 / 上版 / Δ(ms) / Δ%，并标注变快/变慢方向，单位 ms）。
- `diff_runs` 在现有对比内容末尾追加该性能对比块。
- 边界：当前无延迟数据 → 不输出该块（独立「性能（仅记录）」段已显示 N/A）；上版本缺 `latency_summary`（旧报告）→ 输出 ℹ️ 提示"上版本未记录延迟数据，无法对比性能"，不抛错。
- 延续口径：延迟**仅记录、不计分、不否决**，性能对比块同样明确标注，不影响通过率 / regression / improvement 判定。

## Capabilities

### Modified Capabilities
- `reporting`：在"系统必须支持与上次评测的 regression / improvement diff"能力上新增要求——`diff_runs` MUST 额外输出基于 `latency_summary` 的性能（会话延迟）对比块。

## Impact

- 代码：`medeval/reporter/diff.py` 新增 `_latency_diff` 并在 `diff_runs` 接入；新增 `tests/test_diff_latency.py`。
- 行为：报告「与上版本对比」段末尾多一张「性能变化」表；通过率 / regression / improvement 等既有输出与排序不变。
- 兼容性：无 schema 变化、无新依赖；上版本无延迟字段时安全降级为提示，不抛错。
