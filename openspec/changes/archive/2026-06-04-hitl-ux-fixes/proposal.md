# Proposal: HITL 三项体验修复

## Why

HITL 上线后用户反馈三处：
1. 入队过窄——只有红旗失败/needs_human_review/手动才入队，普通 `release_passed=false` 失败漏掉，
   而"所有上线判定失败"都应人工复核。
2. 从用例详情页返回看板会丢失"用例结果"区的筛选条件，来回排查体验差。
3. 失败标签在前端显示英文枚举值（如 `missed_red_flag`），不直观。`FailureTag` 已有 `label_zh`
   单一信任源，应透出给前端。

## What Changes

- **入队规则扩展**：任何 `release_passed=false` 的用例 MUST 入审核队列（新增入队原因 `release_failed`），
  与既有 `needs_human_review` / `red_flag_failed` / `manual` 并列。
- **筛选记忆**：看板"用例结果"筛选条件（上线判定/Level/稳定性/仅看待审）MUST 在跳转用例详情并返回后
  保持，按 run 维度记忆。
- **失败标签中文化**：新增 `GET /api/config/failure-tags` 返回 `{枚举值: label_zh}`（取自 `FailureTag`，
  单一信任源）；前端失败标签 MUST 渲染中文短标签，未知值回退原值。

## Impact

- Affected specs: `eval-platform-service`（入队规则、失败标签元数据接口）、
  `eval-platform-dashboard`（筛选记忆、标签中文化）。
- Affected code: `server/routers/runs.py`（`_queue_reasons`）、`server/routers/config.py`（新端点）、
  `frontend/src/api.ts`、`frontend/src/pages/RunDashboardPage.tsx`、
  `frontend/src/pages/CaseDetailPage.tsx`；测试 `tests/server/test_review_queue.py`。
- 判分内核 `medeval/**` 零改动（仅读取既有 `FailureTag.label_zh`）。
