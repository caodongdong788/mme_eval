## Why

飞书 docx 报告的「失败归因 Top 标签」表格和每条失败 case 的 `**失败标签：**` 行目前直接渲染英文 enum value（`missed_red_flag, constraint_violation, ...`），产研同学读报告时需要心算翻译，且在 docx 表格里 snake_case 看起来像变量名而不是业务标签。`FailureTag._TAG_META` 已经存了一句长 `description`（"红旗症状未触发紧急/急诊建议"），但太长不适合直接当短标签塞进表格和并列展示行。我们要补一个 4~8 字短中文 label 渲染层，让飞书报告读起来"是给人看的失败归因"而不是"代码 dump"。

## What Changes

- `FailureTag` 枚举的元数据 `_TagMeta` 新增 **`label_zh`** 字段（4~8 字短词），覆盖全部 15 个成员（8 个已 emit + 7 个预留）；新增 `FailureTag.label_zh` property
- `medeval/reporter/markdown_report.py` 在「失败归因 Top 标签」表和「失败样本段」标题行使用 `label_zh` 渲染，**英文 enum value 不再出现在 markdown 报告里**
- `report.json` 的 `failure_tags` / `failure_tag_counter` 仍保留英文 enum value 作为机器可读 stable key（**非破坏性，下游消费者无需改动**）
- excel transcript（`excel_transcript.py`）失败标签列保持英文不变（导出物面向下游分析脚本，与 markdown 渲染层解耦）
- `medeval/docs/gen_failure_tags.py` 自动生成的 README 失败标签清单同步使用 `label_zh`，与报告口径统一

## Capabilities

### New Capabilities
（无）

### Modified Capabilities
- `reporting`：「失败归因 Top 标签」与「失败样本段失败标签行」必须显示中文短标签 `label_zh`，不再显示英文 enum value
- `judging-pipeline`：`FailureTag` 元数据扩展为同时携带 `dimension` / `description` / `label_zh`，新增 `FailureTag.label_zh` property 作为公开渲染入口

## Impact

- **代码**
  - `medeval/models.py`：`_TagMeta` 加 `label_zh` 字段、15 个 `_TAG_META` 条目补全短标签、`FailureTag` 加 `label_zh` property、自检 assert 同步
  - `medeval/reporter/markdown_report.py`：新增 `_tag_to_zh_label(tag_str)` helper，2 处渲染（Top 标签表 + 失败样本段标题行）走它
  - `medeval/docs/gen_failure_tags.py`：README 渲染同步使用 `label_zh`
- **数据格式**：`report.json` 不变（依然 emit 英文 enum value）；excel transcript 不变；只有 `report.md` / 飞书 docx 渲染呈现变化
- **测试**：新增 `test_failure_tag_label_zh.py`（元数据覆盖率 / property 行为）、`test_markdown_report.py` 增 case 覆盖中文渲染、`test_excel_transcript.py` 加断言确认导出仍是英文
- **文档**：`README.md` 失败标签清单经 `gen_failure_tags.py` 重新生成
- **依赖**：无新增依赖
- **回归**：单测前后对比 v7 报告肉眼检查；不影响 LLM Judge / 多轮评测 / lark publisher
