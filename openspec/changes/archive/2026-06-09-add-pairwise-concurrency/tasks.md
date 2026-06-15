# Tasks

## 1. 题内并行（medeval/pairwise.py）
- [x] 1.1 `compare_case` 在 `swap_debias=True` 时用 `asyncio.gather` 并行两次 `_judge_order`
- [x] 1.2 单测：断言两次裁判被并发调度且结果与串行一致（消偏/保守语义不变）

## 2. 判分模型携带并发配置（后端）
- [x] 2.1 `JudgeModelConfig` 加 `pairwise_concurrency: int`（默认 4），走既有增量迁移
- [x] 2.2 `schemas`：JudgeModelOut/Create/Update 加 `pairwise_concurrency`
- [x] 2.3 `judge_models` router：create/update 处理新字段，校验 ≥1
- [x] 2.4 单测：CRUD 往返新字段、默认值、边界校验

## 3. 题间并发 + 安全落库（server/pairwise_job.py）
- [x] 3.1 从 `JudgeModelConfig` 读 `pairwise_concurrency` 作为题间并发度
- [x] 3.2 `Semaphore(N)` + `gather` 并发跑 `compare_case`
- [x] 3.3 `asyncio.Lock` 串行化「写 verdict + 递增 done_cases」临界区
- [x] 3.4 单测：并发完成后 verdict 数、done_cases、summary 与串行口径一致

## 4. 前端（frontend）
- [x] 4.1 `api.ts`：JudgeModel / JudgeModelPayload 加 `pairwise_concurrency`
- [x] 4.2 `JudgeModelsPage`：编辑表单加「Pairwise 对比并发」字段（含说明：仅对对比生效）
- [x] 4.3 列表可选展示该并发值

## 5. 验证与归档
- [x] 5.1 `pytest` 全绿
- [x] 5.2 前端 `npm run typecheck` 通过
- [x] 5.3 `medeval run --config config.yaml --dry-run` 通过（评测端零变化自检）
- [x] 5.4 `graphify update .` 刷新图谱
- [x] 5.5 `openspec validate --strict` 通过后 `openspec archive`
