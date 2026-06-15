## Why

上一个 change（`diff-latency-comparison`）在「与上版本对比」段新增了「性能变化」块（含 当前/上版/Δ）。但报告底部仍保留独立的「性能（仅记录）」段，两者在有版本对比时**内容重复**（当前延迟值出现两次），用户反馈冗余。

此外对比块第四列表头用的是 `Δ`，对非技术读者不够直观，宜改为中文「变化」。

## What Changes

- **去重**：独立「性能（仅记录）」段改为**兜底**——仅在该次报告**未呈现**版本对比「性能变化」块时渲染（即无 diff、关闭 diff、或上版本无延迟数据）；有「性能变化」块时不再重复。实现：`render_markdown` 检测 `diff_summary` 是否已含性能块（`"性能变化" in diff_summary`），是则跳过独立段。
- **改名**：`_latency_diff` 对比表第四列表头 `Δ` → `变化`（方向标注 ↑变慢/↓变快不变）。
- 口径不变：延迟仍**仅记录、不计分、不否决**；无对比且无延迟数据时仍显示 N/A 而非空表。

## Capabilities

### Modified Capabilities
- `reporting`：
  - "报告必须呈现延迟统计且标注仅记录不计分"——独立「性能（仅记录）」段改为仅在无版本对比性能块时兜底呈现，消除重复。
  - "diff_runs 必须输出性能（会话延迟）对比块"——对比表第四列列名定为「变化」。

## Impact

- 代码：`medeval/reporter/markdown_report.py`（`render_markdown` 条件渲染独立段）、`medeval/reporter/diff.py`（表头改名）；新增 `tests/test_report_latency_dedup.py`。
- 行为：有 diff 的报告不再出现重复的底部「性能（仅记录）」段；首跑/关闭 diff 时该段照常兜底出现。`test_latency_metrics.py::test_no_latency_data_renders_na`（无 diff 路径）保持绿。
- 兼容性：无 schema 变化、无新依赖。
