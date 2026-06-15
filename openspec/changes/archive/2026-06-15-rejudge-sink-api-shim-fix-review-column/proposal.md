# Proposal: rejudge 下沉 + api shim 迁移 + 修复 review_requested 列

## What Changes

- `review_requested` 加入 `_drop_obsolete_columns`，修复 Postgres 落库 `NotNullViolation`
- 新增 `server/services/rejudge_launch.py`，`rejudge.py` router 变薄
- 前端 `from "../api"` 批量改为 `../api/index`，删除根 `api.ts` shim

## Risks

- rejudge 下沉：保持 HTTP 状态码/文案不变，全量 `test_rejudge_overrides` 回归
- 列删除：仅 DROP 已从 ORM 移除的 `review_requested`
