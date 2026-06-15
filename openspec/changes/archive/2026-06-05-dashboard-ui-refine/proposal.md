# Proposal: 看板 UI 精修（去重复 tab / 饼图 / 双指标柱 / 在线改名 / 精简 meta）

## Why

新设计上线后用户提出五点精修：①「人工审核」tab 与概览待审 KPI、用例明细待审筛选重复；②失败标签分布用饼图更直观；
③分层级通过需同时看数量与通过率；④评测名称需要能在看板直接双击改名（自动保存 + 重名校验），当前只能在发起时定名；
⑤名称下方 meta 信息过多（run_slug/adapter/judge/N），只保留 judge 模型与 N 即可。

①②③⑤为纯前端调整；④需后端补一个 run 改名端点（含重名校验，复用发起评测时的唯一性口径）。

## What Changes

- 看板 MUST 移除「人工审核」标签页（待审信息已由概览 KPI 与用例明细筛选覆盖），标签页保留「概览 / 用例明细」。
- 「失败标签分布」MUST 由水平柱状图改为饼图（含图例与占比）。
- 「分层级通过率」MUST 同时展示每层级的**用例数量**与**通过率**（双轴/组合图），并优化柱形配色与样式。
- 看板评测名称 MUST 支持双击进入编辑、失焦/回车自动保存；保存前 MUST 通过后端校验重名（与已有 run 同名 → 拒绝并提示）。
  - 后端新增 `PATCH /api/runs/{run_id}` 改名端点：空名 → 422；与其它 run 重名 → 409；run 不存在 → 404。
- 名称下方 meta MUST 精简为仅「judge 模型」与「N=<repeat>」两项。

## Impact

- Affected specs: `eval-platform-dashboard`。
- Affected code: `frontend/src/pages/RunDashboardPage.tsx`、`frontend/src/api.ts`（前端）；
  `server/routers/runs.py`、`server/schemas.py`（后端改名端点 + schema）。
- 判分内核 `medeval/**`、数据库 schema 零改动；改名只更新 `EvalRun.name` 字段。
