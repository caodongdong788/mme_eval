# Case Type Dashboard

## Goal

- 运行概览按 Case YAML 的 `case_type` 分类统计成功数、失败数与通过率。
- 使用双柱形图展示数量、折线图展示通过率；类别较多时允许横向浏览。
- `scenario` 继续表示场景，不再作为“类别”图表的统计口径。

## Data flow

1. `RunReport.by_case_type` 在评测汇总阶段按最终 `release_passed` 聚合。
2. `EvalRun.by_case_type` 持久化汇总；既有数据库升级时从 Case 结果回填。
3. Run 详情接口返回 `by_case_type`，前端转换为成功数、失败数、通过率后绘图。

## Verification

- 聚合与数据库测试覆盖分类成功/失败计数。
- 前端单测覆盖分类数据转换和图表内容。
- 前端类型检查、测试与生产构建通过。
