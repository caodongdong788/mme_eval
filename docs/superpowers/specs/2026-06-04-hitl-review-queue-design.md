# 人工审核队列（HITL Review Queue）设计

> 状态：已与用户澄清 4 处设计分叉并定稿。判分内核 `medeval/**` 零改动，纯平台侧（`server/` + `frontend/` + DB）。

## 1. 背景与目标

平台判分全自动（HardGate + Rule + LLM）。两类情况需要人工介入，但当前无落地入口：

- 语义裁决器对**红旗用例规则失败**时不自动救回，置 `needs_human_review=true`——该标志当前是**死路**（无界面消费）。
- 临床专家想纠正机器误判（误杀/漏判），无处记录、无法沉淀。

README 免责声明要求"上线前必须临床专家评审"。本特性把"专家评审"变成平台里**可操作、可追踪、可统计**的旁路流水线。

**铁律**：人工结论**永不回写** verdict / score / `release_passed` / `gate_passed` / `hard_gate_passed`——保 judge 确定性与指纹治理。HITL 是独立旁路层。

## 2. 已定决策（澄清结果）

1. **入队规则** = `needs_human_review=true` ∪（红旗题 且 `release_passed=false`）∪ 手动加入。
2. **"推翻机器"** 仅记 `agree/override` + 备注（可填建议修正文字）；真正改判据复用现有 YAML 编辑页（`derive-yaml`）。
3. **统计** 进看板（人审通过率/分歧率 + 队列计数），**不改 medeval 报告内核**。
4. **不做** 认领/指派/多人复审编排（任何登录人可审，一条可多人留意见）。

## 3. 数据模型

- 新表 `case_annotation`：`id` / `run_id`(FK eval_run.id, index) / `sample_id`(String, index) /
  `reviewer`(String, nullable=登录人显示名) / `verdict`(String：`agree`|`override`) /
  `suggestion`(Text, nullable) / `comment`(Text, nullable) / `created_at`(datetime, default now)。
  一条 (run, sample) 可有多行（多人留意见）。
- `case_result` 追加 1 列 `review_requested`(Boolean default 0)——手动加入队列标记；走现有
  `_ensure_additive_columns` 幂等迁移（旧库 `ALTER TABLE ADD COLUMN`）。
- 复用既有列 `case_result.needs_human_review`、`case_result.release_passed`；红旗判定从
  `detail_json.case.hard_gates.red_flag_triage != "none"` 读（按 run 在内存过滤，~71 条规模，不加 ingest 列）。

## 4. 后端 API（`server/routers/runs.py` + `schemas.py`）

- `GET /api/runs/{run_id}/review-queue`（同 `/cases` 过滤参数）→ `list[ReviewQueueItemOut]`：
  对该 run 的 case_result 行计算入队（三条规则任一）→ 每项含 `sample_id` / `scenario` / `level` /
  `release_passed` / `composite_score` / `failure_tags` / `reasons`(入队原因列表) /
  `reviewed`(是否已审) / `annotations`(已有标注列表)。
- `POST /api/runs/{run_id}/cases/{sample_id}/annotate`（body `AnnotateRequest{verdict, suggestion?, comment?}`）
  → 写一条 annotation，`reviewer` 取飞书登录显示名（可空，dev 放行）。用例不存在于该 run → 404；
  `verdict` 非 `agree`/`override` → 422。
- `POST /api/runs/{run_id}/cases/{sample_id}/request-review` → 置 `review_requested=true`（幂等）。
- `GET /api/runs/{run_id}/review-stats` → `ReviewStatsOut{queue_total, reviewed, pending, agree, override, agree_rate, disagree_rate}`。

`reviewer` 身份复用 `get_current_user_optional` + 显示名（与 benchmarks 的 `_creator_name` 同款）。

## 5. 前端

- `api.ts`：`getReviewQueue` / `annotateCase` / `requestReview` / `getReviewStats` + 类型。
- `RunDashboardPage`：「用例结果」区加「**待审 N**」徽标（来自 review-stats）与「仅看待审」开关；
  顶部统计区加一张卡（人审通过率 / 分歧率 / 待审·已审计数）。**不改 medeval 报告**。
- `CaseDetailPage`：加**裁定面板**——`Radio` 同意/推翻 + 建议修正(`TextArea`) + 备注 + 提交；
  下方 `List` 展示该用例已有 annotations；若选"推翻"，面板提示并给「去改判据(YAML)」按钮（跳回看板 YAML 抽屉，复用 `derive-yaml`）。

## 6. 测试（TDD 先行，`tests/server/test_review_queue.py`）

- 入队三规则：`needs_human_review`命中 / 红旗+失败命中 / `review_requested`命中 / 普通通过用例不入队。
- `annotate` 落库、同一用例多条、`reviewer` 取登录名、非法 verdict 422、未知用例 404。
- `request-review` 置位且幂等。
- `review-stats` 计数与 agree/disagree 率正确。
- `_ensure_additive_columns` 幂等加 `review_requested`（旧库模拟）。
- **不变量**：annotate 后该用例 `release_passed`/`composite_score`/verdicts 不变。
- 前端 `tsc --noEmit` 通过。

## 7. YAGNI / 非目标

- 不做认领/指派/kanban；不在审核面板内嵌结构化或 YAML 改判据；不改 medeval 报告与判分；
  不引入 Monaco 等新前端重组件；不做在线生产链路接入。
