## Why

`add-weighted-scoring-and-grading` 落地了四模块绝对分（安全/合规/功能/体验，满分 1.0）+ 评级，但保留了两处与业务最终口径不一致的设计：

1. **通过/失败口径太松**：评级是叠加产物、不改 `overall_passed`，于是一条用例可能既被判「通过」又只拿 0.82 分。业务方要求收紧为「**非满分即失败**」——只有四模块全部拿满（综合分 1.0）才算通过。
2. **关键词高亮保留了 `red` 富文本标红 + 本地标红文件分支**：飞书 xlsx 导入会把富文本单元格当空白丢弃，该分支对主用法（飞书在线表格查看）无意义，反而是维护负担。

本变更把这两处口径定稿，使代码注释里引用的 `redesign-scoring-modules` 有据可查。

## What Changes

- **失败口径重定义为「非满分即失败」**：报告层在评分后把 `overall_passed` 重定义为「综合分达满分 1.0 才算通过」，其余（含 adapter 出错）一律失败。`RunReport.passed`、各维度切片通过数与 Excel 概览 `passed` 列均按此口径统计。
- **明确评级与通过/失败是两根独立的轴**：评级（优秀/良好/合格/不合格）是质量分档，通过/失败是「是否满分」；一条用例可同时为「良好」且 `overall_passed=False`。
- **保留 stability 三态语义**：`stable_pass/flaky/stable_fail` 仍按 judging 层逐 run 的 `HardGate AND Rule AND 无错` 一致性判定（综合分只在折叠后的代表性 trace 上算一次，无逐 run 综合分）。
- **移除富文本标红 / 本地标红文件逻辑**：命中的 must_have/must_not_have 关键词在对话 cell 内**统一**用 `【关键词】` 纯文本标记；删除 `highlight="red"` 形参、`CellRichText` 富文本分支与相关导入。

## Capabilities

### Modified Capabilities
- `reporting`: 报告层据综合分重定义 `overall_passed`（非满分即失败）；对话流水 Excel 关键词标记统一为 `【】` 纯文本，移除富文本标红。

## Impact

- 代码：`medeval/reporter/scoring.py`（`apply_grading` 据综合分写 `overall_passed`）、`medeval/reporter/aggregator.py`（注释）、`medeval/reporter/excel_transcript.py`（删 `red` 分支与富文本导入，`write_transcripts_xlsx` 去掉 `highlight` 形参）、`medeval/models.py`（注释）、`tests/test_weighted_grading.py`、`tests/test_excel_transcript.py`、`AGENTS.md`、`README.md`。
- 兼容性：`overall_passed` 字段类型不变，仅取值口径变化；历史 `report.json` 仍可加载。`thresholds.overall_pass_rate` 在新口径下变严（要求满分率），由配置控制，不在本变更内调默认值。
- 依赖：不引入新依赖；`openpyxl` 仍用于 xlsx 写盘，但不再依赖其 `rich_text` 子模块。
