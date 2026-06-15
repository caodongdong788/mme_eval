## Why

`reporter/excel_transcript.py` 单文件 423 行，把两类正交关注点揉在一起：

1. **纯内容派生**：文本截断、CJK 字宽折行估算、关键词标记、得分点单元格、维度比率、profile 标签——全是无副作用、易测的纯函数。
2. **openpyxl 排版**：sheet/列宽/行高/冻结窗格/样式写入。

后果：单测要测"标红逻辑"只能整本读懂排版代码；且 `_write_transcripts` 每个 case **调了两次 `resolve_profile`**（`_test_content_cell` 取 name、`_module_max_for_result` 取 module_max）——B 改造后 `resolve_profile` 每次都 `ScoringCfg.model_validate`，71 题白白解析 142 次。

研发阶段做一次纯结构解耦：拆出可测的内容派生层，并把每题 profile 解析收敛为一次。

## What Changes

- 新增 `medeval/reporter/transcript_cells.py`：承载所有**纯内容派生** helper 与相关常量（`_display_lines` / `_truncate` / `_turns` / `_user_turn_count` / `_fmt_points` / `_fmt_dim_ratio` / `_case_title` / `_test_content_cell` / `_deduction_text` / `_scoring_point_cells` / `_highlight_runs` / `_mark_plain` / `_turn_cell` / `_PROFILE_ZH` 等）。
- `excel_transcript.py` 收敛为**排版/写入层**：`_write_overview` / `_write_transcripts` / `write_transcripts_xlsx` + 布局常量，从 `transcript_cells` 导入内容派生函数。
- **每题只解析一次 profile**：`_write_transcripts` 对每个 case 调一次 `resolve_profile`，把 `module_max` 与 `name` 传给内容派生函数；删除 `_module_max_for_result`，`_test_content_cell(result, profile_name)` 改收已解析的 profile 名。

## Capabilities

### Modified Capabilities
- `reporting`：新增要求"transcripts.xlsx 的内容派生与 openpyxl 排版 MUST 分层；每个 case 的评分 profile 在导出时 MUST 至多解析一次"。

## Impact

- 代码：新增 `medeval/reporter/transcript_cells.py`；`excel_transcript.py` 改为导入；`reporter/__init__.py` 公开 API（`write_transcripts_xlsx`）不变；新增 `tests/test_transcript_cells.py`。
- 行为：**xlsx 产物逐字节等价**（纯函数搬家 + 解析次数收敛，无内容/样式变化）。现有 `tests/test_excel_transcript.py`（走公开 `write_transcripts_xlsx`）保持绿。
- 兼容性：公开导出不变；无配置/schema 变化；不引入新依赖。
