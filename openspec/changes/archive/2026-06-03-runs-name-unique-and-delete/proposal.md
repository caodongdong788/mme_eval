## Why

评测列表里多次评测易出现重名，难以区分；且列表只能查看、无法清理历史 run。需要在发起
评测时保证名称唯一，并支持在列表中删除 run。

## What Changes

- 发起评测时校验 run 名称唯一：若最终名称（`run_name` 或缺省的 benchmark 名）与已有 run 重名，返回 409 并提示换名。
- 新增删除 run 接口 `DELETE /api/runs/{run_id}`：删除该 run 及其用例结果（级联），并清理 `outputs/<run_slug>` 产物目录；运行中/等待中的 run 不可删除。
- 前端评测列表：各列宽改为内容自适应；操作栏新增「删除」（二次确认）。

## Capabilities

### Modified Capabilities
- `eval-platform-service`: 发起评测新增名称唯一性约束；新增删除 run 的 REST 能力。

## Impact

- 修改：`server/routers/runs.py`（create_run 唯一性校验 + 新增 delete 端点）、
  `frontend/src/pages/RunsPage.tsx`（列自适应 + 删除）、`frontend/src/api.ts`（deleteRun）。
- 测试：`tests/server/test_api.py` 增重名 409、删除成功/404/运行中拒绝用例。
