## 1. 失败口径：非满分即失败

- [x] 1.1 `reporter/scoring.py::apply_grading` 写完综合分后，据 `composite_score >= 1.0 且 trace.error is None` 重定义 `r.overall_passed`
- [x] 1.2 确认 `reporter/aggregator.py::build_report` 在 `apply_grading` 之后聚合 `passed` / 各维度切片，使其按新口径统计；更新相关注释
- [x] 1.3 `models.py` 更新 `CaseResult.overall_passed` 与 grading 相关字段注释，说明报告层重定义口径

## 2. 移除富文本标红 / 本地标红文件

- [x] 2.1 `reporter/excel_transcript.py` 删除 `highlight` 形参、`red` 富文本分支、`_RED_FONT` 与 `CellRichText/TextBlock/InlineFont` 导入
- [x] 2.2 `_turn_cell` 改为只返回 `【】` 纯文本标记；`write_transcripts_xlsx(report, path)` 收敛为两参签名
- [x] 2.3 更新模块 docstring，说明只保留 `【】` 纯文本标记

## 3. 测试

- [x] 3.1 `tests/test_weighted_grading.py`：把「评级不改 overall_passed」改为「非满分即失败」+「满分判通过」用例
- [x] 3.2 `tests/test_excel_transcript.py`：删除 `red` 富文本用例，保留 `【】` 纯文本标记断言
- [x] 3.3 全量 `pytest` 通过（199 passed）

## 4. 规格与知识库

- [x] 4.1 `openspec/specs/reporting/spec.md`：四模块/评级需求加「非满分即失败」口径与场景；transcripts 需求改为 `【】` 纯文本、移除 `red`
- [x] 4.2 `openspec/specs/judging-pipeline/spec.md`：在 `overall_passed` 定义处加交叉引用（报告层会重定义）
- [x] 4.3 `AGENTS.md` / `README.md` 更新到最新评分/失败口径与关键词标记说明
