# Proposal: 人工审核队列（HITL Review Queue）

## Why

平台判分全自动，但语义裁决器对红旗用例规则失败时置的 `needs_human_review=true` 当前是**死路**
（无界面消费），临床专家也无处记录/沉淀对机器判分的纠正。README 免责声明要求"上线前必须临床
专家评审"。本特性把"专家评审"变成平台里可操作、可追踪、可统计的**旁路**流水线，并与既有
`derive-yaml`（改判据另存新 benchmark）形成"失败→金样本"闭环。

详见设计文档 `docs/superpowers/specs/2026-06-04-hitl-review-queue-design.md`。

## What Changes

- 新增**审核队列**：某 run 的用例入队当且仅当 `needs_human_review=true` ∪（红旗题且 `release_passed=false`）
  ∪ 手动加入（`review_requested`）。
- 新增**裁定记录**：专家对入队用例记 `agree`/`override` + 建议修正 + 备注，`reviewer` 取飞书登录身份。
  人工结论 MUST NOT 回写任何判分字段（verdict/score/release_passed/gate_passed/hard_gate_passed）。
- 新增**看板统计**：人审通过率 / 分歧率 / 待审·已审计数。
- 后端：新表 `case_annotation`，`case_result` 追加 `review_requested` 列（幂等迁移）；新增
  `review-queue` / `annotate` / `request-review` / `review-stats` 端点。
- 前端：看板待审徽标 + 筛选 + 统计卡；用例详情页裁定面板（推翻时给「去改判据(YAML)」入口复用 `derive-yaml`）。

## Impact

- Affected specs: `eval-platform-service`（+审核队列与裁定）、`eval-platform-dashboard`（+审核界面）。
- Affected code: `server/models_db.py`、`server/db.py`、`server/ingest.py`(无需改，复用现列)、
  `server/schemas.py`、`server/routers/runs.py`、`frontend/src/api.ts`、
  `frontend/src/pages/RunDashboardPage.tsx`、`frontend/src/pages/CaseDetailPage.tsx`、
  新增 `tests/server/test_review_queue.py`。
- 判分内核 `medeval/**` 零改动。
- 非目标：认领/指派/多人复审编排、审核内嵌改判据、在线生产链路、改 medeval 报告。
