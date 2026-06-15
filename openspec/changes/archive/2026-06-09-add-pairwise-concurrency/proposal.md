# Proposal: Pairwise 对比并发加速 + 并发配置外显

## Why

Pairwise 对比当前**三层全串行**：`run_pairwise_comparison` 逐题 `for` 循环，`compare_case`
内部位置消偏的两次裁判调用也串行。一次 71 题全量对比 = 71 × 2 = 142 次裁判调用排队执行，
单次裁判 ~3–5s 时总耗时约 7–12 分钟，进度条推进缓慢、体验差。

主评测链路（`medeval/runner`、`service.py`）早已用 `asyncio.Semaphore + gather` 并发，
Pairwise 是后补功能未复用该范式。本变更只优化 Pairwise，**不触碰主评测判分链路**。

## What Changes

- **题内并行**：`PairwiseComparator.compare_case` 在 `swap_debias=True` 时用
  `asyncio.gather` 并行跑顺序①/顺序②两次裁判调用（默认行为，不暴露开关）。单题耗时约减半。
- **题间并发**：`run_pairwise_comparison` 用 `asyncio.Semaphore(N)` + `gather` 让多道题
  同时比较；并发写库与 `done_cases` 进度更新由 `asyncio.Lock` 串行化，避免 SQLite 写冲突
  与进度跳变。
- **并发可配且外显**：`JudgeModelConfig` 新增 `pairwise_concurrency` 字段（题间并发度，
  默认 4），在「判分模型」编辑页可视可配。该配置**仅对 Pairwise 对比生效**，对主评测端
  无影响。
- 配套：`schemas`（JudgeModelOut/Create/Update）、`judge_models` router CRUD、前端
  `api.ts` 类型与 `JudgeModelsPage` 表单字段。

## Impact

- Affected specs: `judging-pipeline`（Pairwise 比较器并发执行语义）
- Affected code:
  - `medeval/pairwise.py`（题内 gather）
  - `server/models_db.py`（JudgeModelConfig 加列，走既有增量迁移）
  - `server/schemas.py`、`server/routers/judge_models.py`
  - `server/pairwise_job.py`（题间并发 + 锁保护落库；从模型配置读并发度）
  - `frontend/src/api.ts`、`frontend/src/pages/JudgeModelsPage.tsx`
- 兼容性：`pairwise_concurrency` 带默认值 4，旧判分模型行自动获默认；`compare_case` 输出
  语义不变（仅执行方式从串行改并行），`fingerprint` 不变（并发不属判分语义）。
- 不改变 `release_passed`/`gate_passed`/`hard_gate.*`；Pairwise 仍是相对偏好、不进 gate。
