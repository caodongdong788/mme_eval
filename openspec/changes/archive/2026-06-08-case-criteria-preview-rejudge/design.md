## Context

平台现有「改判据 → 重判」闭环刻意三段解耦：HITL 裁定（`CaseAnnotation` 旁路、永不回写分）、判据编辑（看板 `EditCriteriaDrawer` 按过滤子集整包编辑，`derive-yaml` 另存 / `overwrite-yaml` 覆盖，内置不可覆盖）、重判（`POST /api/runs/{id}/rejudge` 传 `cases_benchmark_id` 整包替换判据，冻结 trace 零 bot 调用经 `judge_traces` 重跑）。

审核者在用例明细页发现某条用例判据有误时，只能跳看板按过滤整包编辑、且改前无法验证。本设计在**不破坏上述三段解耦与「run 冻结结果不可变 / 可 diff」治理**的前提下，补一个就地的「改 → 单条试判预览 → 覆盖当前 benchmark」闭环。

约束：
- 内核侧 `judge_traces`（`medeval/service.py`）已声明纯判分、零 adapter；`score_case`（`medeval/reporter/scoring.py`）按 profile 重算四维分与上线判定。可直接复用。
- 判据可覆盖字段固定为 `_CASE_OVERRIDE_FIELDS = (expected_behavior, hard_gates, rubric, scoring_points)`（`server/benchmarks.py`），合并走 `_apply_case_overrides`。
- 当前 run 关联 benchmark 若为 builtin 则不可覆盖（沿用现状，前端 disable + 提示另存）。

## Goals / Non-Goals

**Goals:**
- 用例明细页就地编辑**单条**用例判据（复用 `EditCriteriaDrawer`，只装该 `sample_id` 的 YAML）。
- 单条 **ephemeral 试判预览**：用编辑后判据 + 该用例冻结 trace 重算，返回新 verdict / 四维分 / 上线判定 + 与当前值 diff；不落库、不产 run、不回写、不动 HITL 旁路。
- 满意后复用现成「覆盖当前 benchmark」（`overwrite-yaml`）把判据落回这次评测当前 benchmark。
- 编辑判据时显式展示当前 benchmark `#id「名称」`。

**Non-Goals:**
- 不写回当前 run 的任何判分（方案 A，明确排除方案 B）。
- 不在本变更里做「批量攒 + 一次性重判」的购物车（后续可基于此扩展；收尾仍走现有正式 rejudge 产新 run）。
- 不改 `TestCase` / `BaseJudge` / `FailureTag` 核心 schema；不放开内置 benchmark 覆盖限制。
- 不改判据 fingerprint 逻辑（preview 仅观测，不进任何持久化 fingerprint）。

## Decisions

**D1：单条试判做成 ephemeral 端点，零持久化。**
新增 `POST /api/runs/{run_id}/cases/{sample_id}/preview-rejudge`，请求体携带编辑后判据（结构化 `CaseLogicOverride` 或单条 YAML，二选一见 D2）。后端：取该 run 冻结的该用例 `TestCase` + 其 `ConversationTrace`（复用 `_frozen_cases_and_traces` 逻辑，按 `sample_id` 取单条）→ 套用判据 patch → `judge_traces` 跑 1 条 → `score_case` 重算 → 组装响应。**全程不写库、不建 run 目录、不复制留痕。**
- 备选：复用 `rejudge` 端点加 `dry_run` 参数。否决——rejudge 语义是"产新 run"，塞预览会污染其职责，且 rejudge 走整 run 落库链路，单条预览复用代价高。

**D2：preview 请求体用结构化 `CaseLogicOverride`（按 `sample_id`），而非整段 YAML。**
前端编辑器虽是 YAML，但提交预览时只需该条的 4 个判据字段；后端用 `_apply_case_overrides` 同一套合并语义，避免 YAML 解析歧义。
- 备选：直接传 YAML 文本。否决——单条预览没必要承担整包 YAML 解析/校验；但 `cases-yaml` 仍提供 YAML 用于编辑器展示。

**D3：`cases-yaml` 端点增 `sample_id` 过滤参数，复用现有 YAML 导出。**
`GET /api/runs/{run_id}/cases-yaml?sample_id=<sid>` 只导出该条用例 YAML，前端用它预填 `EditCriteriaDrawer`。与看板「按过滤子集」共用同一导出路径，仅多一个过滤维度。

**D4：前端复用 `EditCriteriaDrawer`，不新造编辑器。**
用例明细页 HITL 卡片把「去改判据(YAML)」从 `navigate` 改为就地打开同一抽屉，注入单条 YAML、当前 benchmark 名称、以及「覆盖当前 benchmark / 另存新 benchmark」既有处理器。抽屉新增一个**当前 benchmark 名称**展示项（`#id「名称」`），看板入口也一并受益。

**D5：试判预览与覆盖 benchmark 解耦呈现。**
预览只读、可反复试；覆盖是显式独立动作（沿用现成 danger 二次确认）。明确告知用户：覆盖改的是判据源（影响后续评测/重判），当前 run 已存分不变；要得到修正后的 run 仍需正式 rejudge。

## Risks / Trade-offs

- [用户误以为预览=已生效，或覆盖后当前 run 分该变] → 预览结果区与抽屉文案明确标注「仅预览，不改当前 run」「覆盖仅改判据源，需另跑重判」。
- [单条取冻结 trace：N>1 run 的代表 trace 选取] → 复用 `judge_traces` / 现有 rejudge 的代表 trace 选取逻辑，保持与正式 rejudge 一致，避免预览与正式重判口径不一。
- [当前 run benchmark 为 builtin 不可覆盖] → 沿用现状：抽屉 disable「覆盖」并提示改用「另存为新 benchmark」。
- [preview 端点被高频调用的开销] → 单条 judge 调用；与正式 rejudge 单条等价，开销可控；不加缓存。

## Migration Plan

纯增量：新增一个只读端点 + 一个查询参数 + 前端入口与展示项，无 DB schema 变更、无数据迁移、无破坏性改动。回滚即移除端点/参数与前端入口，现有看板编辑/重判链路不受影响。
