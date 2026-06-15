# Proposal: 得分点惩罚项展示 + 指南匹配率展示与过滤

## Why

1. **惩罚型得分点显示「0/0」难懂**：负分（"出现即惩罚"）得分点在未触发时 `score=0 / max_score=0`，用例详情得分点表显示成 `0/0`，看不出这是「扣分项·未触发」。应像对话流水那样把符号/罚则与说明讲清楚。
2. **指南匹配率没在用例详情露出**：`CaseResult.guideline_match_rate` 已计算但前端用例详情未展示；用户需要以「得分 100%（命中/总数）」形式看到，并能在用例列表按指南匹配率过滤。

## What Changes

1. **得分点惩罚项展示**：用例详情「得分点」表 MUST 区分正分点与惩罚（负分）点——惩罚点未触发显示「未触发·罚则 -N」、已触发显示「已扣 -N」，不再显示无意义的 `0/0`；说明列 MUST 带出该点的符号/判据，使扣分性质清晰。
2. **用例详情指南匹配率**：用例详情 MUST 新增「指南匹配率」，以 `X%（matched/total）` 形式展示（matched/total 为带指南锚点得分点的命中数/总数）；无带锚点得分点时显示「无指南锚点」。
3. **指南匹配率过滤**：用例列表 MUST 新增「指南匹配率」过滤（100% / <100% / 无指南锚点），服务端按 `guideline_match_rate` 列过滤。

## Impact

- Affected specs: `eval-platform-dashboard`。
- Affected code：
  - 前端 `CaseDetailPage.tsx`（得分点表惩罚展示、指南匹配率项）。
  - 前端 `RunDashboardPage.tsx`（指南匹配率过滤 Select）。
  - 后端 `server/routers/runs.py::_filtered_case_rows` + `list_case_results`（含 cases-yaml/export 一致）：新增 `guideline` 过滤参数。
- 纯展示 + 列表过滤，不改判分内核、不动 HardGate / 评分口径。
