# Proposal: 平台可调配置重判 + 改 case 判据派生新 benchmark + benchmark 上传人

## Why

平台已支持「离线重判」，但重判**写死复用源 run 的配置**——用户想"换个判分口径/换个 judge 模型/改某条 case 的判据再看分"时，只能去改服务器 `config.yaml` 或 `cases/*.yaml` 再重新发布，流程重、且会污染线上配置与内置用例集。

需要把"调配置→重判"做成**网页上的轻量操作**，且：

- 调判分口径（权重/阈值）与换 judge 模型 → **随重判请求临时生效**，不改 `config.yaml`、不重新发布；
- 改 case 判断逻辑（must_have/must_not_have、红旗/处方/免责、rubric）→ **派生一个新 benchmark**（不动原 benchmark / 内置用例集），再按新判据重判；
- benchmark 列表能看出**谁建的**（上传人），便于多人区分。

## What Changes

- **重判可带配置覆盖**：`POST /api/runs/{id}/rejudge` 接收可选 body——`scoring`（覆盖四模块权重/阈值/扣分步长/pass_rule）、`judge`（覆盖 LLM judge 的 provider/model/base_url/api_key）、`cases_benchmark_id`（用某 benchmark 的 case 判据替换冻结用例）。覆盖仅作用于本次重判，bot 回答仍冻结。
- **改 case 判据 → 派生新 benchmark**：新增 `POST /api/benchmarks/{id}/derive`——复制源 benchmark 全部用例，按 `sample_id` 套用 `expected_behavior`/`hard_gates`/`rubric` 覆盖，schema 校验通过后**另存为新的 uploaded benchmark**（`created_by`=当前登录人），**不修改源 benchmark**。前端在用例详情页编辑判据后「另存为新 benchmark 并重判」：先 derive，再以 `cases_benchmark_id=新bm` 重判。
- **benchmark 上传人**：上传 / 派生时写入 `Benchmark.created_by`（复用既有列），`BenchmarkOut` 透出，前端列表新增「上传人」列。

## Impact

- Affected specs: `eval-platform-service`（重判覆盖、派生 benchmark、上传人/REST API）、`eval-platform-dashboard`（重判弹框、判据编辑器、上传人列）。
- Affected code: `server/eval_job.py`、`server/routers/runs.py`、`server/routers/benchmarks.py`、`server/benchmarks.py`、`server/schemas.py`、`frontend/src/api.ts`、`frontend/src/pages/RunDashboardPage.tsx`、`frontend/src/pages/CaseDetailPage.tsx`、`frontend/src/pages/BenchmarksPage.tsx`。
- 判分内核 `medeval/**` **零改动**（复用 `judge_traces` / `config.ScoringCfg` / `loader` / `TestCase`）。
- 非目标（后续）：rubric 的可视化编辑（v1 后端通用支持、前端先做 hard_gates + expected_behavior）、派生 benchmark 的血缘图、覆盖配置的"存为预设"。
