# Proposal: 用例结果表增加「人审结果」列

## Why

HITL 裁定目前只能在用例详情页看到，看板"用例结果"列表无法一眼看出哪些用例已被人工同意/推翻。
用户需要在列表里直接看到人审结论，并悬浮查看建议与备注。

## What Changes

- `GET /api/runs/{run_id}/cases` 返回的每条用例 SHALL 附带 `review` 摘要：该用例**最新一条**人工裁定的
  `verdict`（agree/override）、`reviewer`、`suggestion`、`comment` 与裁定条数 `count`；无裁定为 null。
- 看板"用例结果"表 SHALL 新增「人审结果」列，渲染「同意/推翻」标签，悬浮（tooltip）展示建议与备注。

## Impact

- Affected specs: `eval-platform-service`（cases 列表附人审摘要）、`eval-platform-dashboard`（人审列）。
- Affected code: `server/schemas.py`、`server/routers/runs.py`（list_case_results）、
  `frontend/src/api.ts`、`frontend/src/pages/RunDashboardPage.tsx`；测试 `tests/server/test_review_queue.py`。
- 判分内核 `medeval/**` 零改动；人审摘要为只读旁路，MUST NOT 影响判分字段。
