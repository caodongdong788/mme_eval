# Refactor Layering Implementation Plan

> **SUPERSEDED** — 设计见同目录 `2026-06-15-refactor-layering-design.md`；实施已归档（`refactor-layering-debt` 及 `server-layering-*` / `frontend-layering-*`）。索引见 [`docs/superpowers/README.md`](../README.md)。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在零行为变更前提下，完成目录分层、Server/Frontend 解耦、重复逻辑消除、Judge 标签前后端对齐与基础容错补强。

**Architecture:** P0 在 `medeval/` 建立单一信任源并暴露只读 config API → P1 拆分 `runs` router 与 `eval_job` → P2 拆分 `api.ts` 与大页面 → P3 目录归位与日志。每阶段全量 `pytest` 门禁。

**Tech Stack:** Python 3.10+ / FastAPI / SQLAlchemy / medeval 内核 / React+TS+Vite+AntD（无新依赖）

**Design spec:** `docs/superpowers/specs/2026-06-15-refactor-layering-design.md`

---

## Phase 0 — 治理与 OpenSpec（全阶段前置）

**Files:**
- Create: `openspec/changes/refactor-layering-debt/proposal.md`
- Create: `openspec/changes/refactor-layering-debt/tasks.md`
- Create: `openspec/changes/refactor-layering-debt/specs/eval-platform-service/spec.md`（delta：结构 SHALL 保持 API 等价）
- Create: `openspec/changes/refactor-layering-debt/specs/evaluation-cli/spec.md`（delta：CLI 行为 SHALL 不变）

- [ ] **Step 1:** 运行 `graphify update .`
- [ ] **Step 2:** 撰写 proposal（含非目标、风险、分阶段交付）
- [ ] **Step 3:** 运行 `openspec validate refactor-layering-debt --strict`

---

## Phase P0 — 共享去重 + Judge 标签对齐

### Task P0-1: `medeval/judge_labels.py`

**Files:**
- Create: `medeval/judge_labels.py`
- Create: `tests/test_judge_labels.py`
- Modify: `server/compare.py`（改用 `FINGERPRINT_LABELS`）
- Test: `tests/server/test_compare.py`（若有）或 `test_api.py` diff 相关

- [ ] **Step 1:** 写失败测试 — `judge_verdict_label("hard_gate.red_flag") == "硬门槛·红旗分诊"`
- [ ] **Step 2:** 写失败测试 — `judge_verdict_label("llm.triage_quality") == "体验·分诊建议"`（补全维度）
- [ ] **Step 3:** 实现 `judge_verdict_label` + `FINGERPRINT_LABELS`
- [ ] **Step 4:** 改 `compare.py` 引用；跑 `pytest tests/test_judge_labels.py -v`

### Task P0-2: API `GET /api/config/judge-verdict-labels`

**Files:**
- Modify: `server/routers/config.py`
- Create: `tests/server/test_config_judge_labels.py`

- [ ] **Step 1:** 写失败测试 — GET 返回 200，含 `hard_gate.red_flag`、`llm.empathy`
- [ ] **Step 2:** 实现端点：导出预置 verdict 表（由 `judge_labels` 生成）
- [ ] **Step 3:** `pytest tests/server/test_config_judge_labels.py -v`

### Task P0-3: 前端消费 Judge 标签 API

**Files:**
- Create: `frontend/src/judgeVerdictLabels.ts`（镜像 `failureTags.ts`）
- Modify: `frontend/src/utils/caseJudging.ts`
- Modify: `frontend/src/api.ts`（或 `api/config.ts` 若已拆）— `getJudgeVerdictLabels()`
- Modify: 使用 `judgeLabel` 的组件（`JudgeVerdictTable.tsx` 等）传入 hook 或包装函数
- Test: `frontend/src/utils/caseJudging.test.ts`

- [ ] **Step 1:** API 客户端方法 + 模块缓存 hook
- [ ] **Step 2:** `judgeLabel` 读缓存，未命中回退 `name`
- [ ] **Step 3:** 更新/新增前端单测；`npm test` 通过

### Task P0-4: Token / cost 去重

**Files:**
- Create: `medeval/reporter/token_cost.py`
- Modify: `medeval/reporter/aggregator.py`
- Modify: `server/ingest.py`
- Create: `tests/test_token_cost.py`

- [ ] **Step 1:** 从 ingest 复制 characterization fixture（`CaseResult` 样例）
- [ ] **Step 2:** 断言 refactor 前后 `(total, cost)` 一致 — 先红
- [ ] **Step 3:** 抽取 `case_token_cost`；aggregator + ingest 调用
- [ ] **Step 4:** `pytest tests/test_token_cost.py tests/server/test_ingest.py -v`

### Task P0-5: Config overrides 抽取

**Files:**
- Create: `server/services/__init__.py`
- Create: `server/services/config_overrides.py`
- Modify: `server/eval_job.py`（re-export）
- Test: `tests/server/test_rejudge_overrides.py`

- [ ] **Step 1:** 迁函数，eval_job 保留 `from .services.config_overrides import ...`
- [ ] **Step 2:** 全量 server 评测相关测试绿

### P0 验收

- [ ] `pytest`
- [ ] `medeval run --config config.yaml --dry-run`
- [ ] `graphify update .`
- [ ] 勾选 `openspec/changes/refactor-layering-debt/tasks.md` P0 项

---

## Phase P1 — Server 解耦

### Task P1-1: 拆分 `runs` router

**Files:**
- Create: `server/routers/runs/__init__.py`
- Create: `server/routers/runs/_helpers.py`
- Create: `server/routers/runs/crud.py`
- Create: `server/routers/runs/rejudge.py`
- Create: `server/routers/runs/review.py`
- Create: `server/routers/runs/cases.py`
- Delete: `server/routers/runs.py`（内容迁尽后）
- Modify: `server/app.py`（import 路径若需调整）

- [ ] **Step 1:** 先迁 `_helpers` + `crud`，`__init__.py` include_router
- [ ] **Step 2:** 迁 `rejudge` / `review` / `cases`
- [ ] **Step 3:** `pytest tests/server/test_api.py tests/server/test_review_queue.py tests/server/test_runs_rename.py -v`
- [ ] **Step 4:** 确认原 `runs.py` 行数 <50（仅 re-export 或删除）

### Task P1-2: 拆分 `eval_job`

**Files:**
- Create: `server/services/eval_launch.py`
- Create: `server/services/eval_rejudge.py`
- Create: `server/services/eval_resume.py`
- Create: `server/services/eval_artifacts.py`
- Modify: `server/eval_job.py`（re-export 公开符号）

- [ ] **Step 1:** 按函数边界剪切，保留 `eval_job.run_*` 入口名
- [ ] **Step 2:** `pytest tests/server/test_eval_job.py tests/server/test_persist_rejudge_resume.py -v`

### P1 验收

- [ ] 全量 `pytest`
- [ ] `graphify update .`

---

## Phase P2 — Frontend 解耦

### Task P2-1: 拆分 `api.ts`

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/runs.ts`, `benchmarks.ts`, `pairwise.ts`, `config.ts`, `auth.ts`, `index.ts`
- Modify: `frontend/src/api.ts` → re-export

- [ ] **Step 1:** 抽 `client.ts`（axios/fetch 封装）
- [ ] **Step 2:** 按域迁方法，`api` 对象聚合不变
- [ ] **Step 3:** `npm run build` + 前端测试绿

### Task P2-2: 大页面 hooks 化

**Files:**
- Create: `frontend/src/hooks/useRunDashboard.ts`
- Create: `frontend/src/hooks/usePairwiseDetail.ts`
- Modify: `RunDashboardPage.tsx`, `PairwiseDetailPage.tsx`

- [ ] **Step 1:** 提取数据加载与 filter 状态到 hook
- [ ] **Step 2:** 页面仅编排布局；行为快照测试若有则跑绿

### P2 验收

- [ ] `npm test` + `npm run build`
- [ ] 手动冒烟：Runs 列表 → Dashboard → Case 明细 Judge 表中文正常

---

## Phase P3 — 收尾

### Task P3-1: 目录归位

**Files:**
- Move: `calibration/compute_agreement.py` → `scripts/compute_agreement.py`
- Move: `.aidp_proxy.py` → `scripts/aidp_proxy.py`
- Modify: `MIGRATION.md` / `README.md` 路径引用

- [ ] **Step 1:** git mv + 修正 import/文档
- [ ] **Step 2:** 无测试破坏（calibration 无 CI 则跳过）

### Task P3-2: 日志与 except 收窄

**Files:**
- Modify: `server/eval_job.py`, `medeval/observability/langfuse_tracing.py`（仅补 log context）

- [ ] **Step 1:** 关键 except 块加 `logger.exception(..., extra={"run_id": ...})`
- [ ] **Step 2:** 确认 Langfuse 未配置时仍 no-op

### Task P3-3: 文档

- Modify: `AGENTS.md` — aggregator 命名对照表

### P3 验收 + 归档

- [ ] 全量 `pytest` + `medeval run --dry-run`
- [ ] `graphify update .`
- [ ] `openspec validate --strict` → `openspec archive refactor-layering-debt`

---

## 依赖关系图

```
P0-1 judge_labels ──┬── P0-2 API ── P0-3 前端
P0-4 token_cost     │
P0-5 overrides      │
        └───────────┴──> P1 runs/eval_job ──> P2 api/pages ──> P3
```

**建议 PR 切分：** `refactor/p0-judge-labels` · `refactor/p0-dedup` · `refactor/p1-server` · `refactor/p2-frontend` · `refactor/p3-cleanup`

---

## 回滚策略

每 PR 独立可 revert；P0 若有标签展示争议，前端可临时回退读本地表 while 保留 API（不推荐长期）。
