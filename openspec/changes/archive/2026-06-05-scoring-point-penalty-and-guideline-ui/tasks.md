# Tasks

## 后端：指南匹配率过滤
- [x] 1.1 `server/routers/runs.py::_filtered_case_rows` 增 `guideline` 参数（full/partial/none）
- [x] 1.2 `list_case_results` / `get_cases_yaml` / export 透传 `guideline`
- [x] 1.3 测试：full→仅 rate≈1.0；partial→rate 非空且<1；none→rate 为空（4 passed）

## 前端：展示
- [x] 2.1 `CaseDetailPage` 得分点表：惩罚点显示「未触发·罚则 -N」/「已扣 -N」，说明带符号判据
- [x] 2.2 `CaseDetailPage` 新增「指南匹配率」= `X%（matched/total）`，无锚点显示「无指南锚点」
- [x] 2.3 `RunDashboardPage` 过滤栏新增「指南匹配率」Select（100%/<100%/无指南锚点）

## 验证
- [x] 3.1 `pytest` 全量绿（541 passed）；前端 tsc + build
- [x] 3.2 `graphify update .`；`openspec validate --strict` 后 archive；同步文档
