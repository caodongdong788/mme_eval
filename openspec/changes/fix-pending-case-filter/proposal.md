# Proposal: 用例明细「仅看待审」条数与列表不一致

## Why

`/runs/{id}/cases` 默认 `limit=50` 且前端未翻页；「仅看待审」在客户端对前 50 条再过滤，而角标 `待审 32/32` 统计全队列，导致列表少于待审总数。

## What

- 后端 `list_case_results` 增加 `review_pending=true`：在分页前筛出「入队且未裁定」用例
- 前端开启「仅看待审」时传 `review_pending`；列表请求 `limit=100`（覆盖当前 benchmark 规模）
