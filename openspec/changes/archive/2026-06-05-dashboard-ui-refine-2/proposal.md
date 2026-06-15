# Proposal: 看板二次精修（性能成本同行 / 对话轮数展示+过滤 / 详情中文映射）

## Why

用户继续提三点：①「性能（延迟）」与「成本/Token」两张卡各占一行太占空间，应并排一行；
②用例明细需展示每条用例的对话轮数，并能按轮数过滤；③用例详情页的「评分档 / 稳定性」值、
「维度分 / 扣分原因」的 key、Judge 列的 key 都是英文，应中文映射，便于非技术评审阅读。

①③为纯前端；②需后端在用例列表返回对话轮数并支持轮数过滤——轮数可由已落库的 `detail_json`
推导（用例 turns / trace 的 user 轮数），**无需新增数据库列与迁移**。

## What Changes

- 概览「性能（延迟）」与「成本/Token」MUST 并排为一行（各占一半宽度）。
- 用例明细 MUST 展示每条用例的「轮数」列；并 MUST 新增「对话轮数」过滤（单轮 / 多轮），可与其它筛选叠加、随筛选记忆。
  - 后端 `GET /api/runs/{run_id}/cases` MUST 在每行返回 `n_turns`（由 `detail_json` 推导），并支持 `turns=single|multi` 过滤。
- 用例详情页 MUST 对以下值做中文映射展示：评分档（profile）、稳定性（stability）、维度分/扣分原因的维度 key（safety/compliance/function/experience）、Judge 列的 judge key（hard_gate.*/rule.*/llm.*/scoring_point.*）。

## Impact

- Affected specs: `eval-platform-dashboard`。
- Affected code: 后端 `server/schemas.py`（`CaseRowOut.n_turns`）、`server/routers/runs.py`（推导+过滤）；
  前端 `frontend/src/api.ts`（`CaseRow.n_turns`）、`RunDashboardPage.tsx`（同行卡 + 轮数列/过滤）、`CaseDetailPage.tsx`（中文映射）。
- 判分内核 `medeval/**` 与数据库 schema 零改动（轮数从 `detail_json` 推导，不新增列）。
