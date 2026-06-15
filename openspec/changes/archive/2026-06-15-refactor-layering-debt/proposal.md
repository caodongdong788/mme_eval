# Proposal: Refactor Layering Debt（P0 共享去重 + Judge 标签）

## Why

平台层存在巨型模块（`runs.py` / `eval_job.py` / `api.ts`）、token/cost 重复计算、Judge 展示标签前后端不一致。需在**零行为变更**前提下降低维护成本。

## What Changes（P0 范围）

- 新增 `medeval/judge_labels.py` 单一信任源；`GET /api/config/judge-verdict-labels`（additive）
- 前端 `useJudgeVerdictLabels` 消费 API，未知 verdict 回退 raw name
- 抽取 `medeval/reporter/token_cost.py`；`ingest` 与 `aggregator` 共用
- 抽取 `server/services/config_overrides.py`；`eval_job` re-export

## Non-Goals（P0）

- 不拆 `runs.py` / `eval_job` 体量（P1）
- 不改判分、API 路径、JSON 字段、CLI 行为
- 不引入新框架或升级依赖

## Risks

- 标签展示补全维度可能被误认为业务变更 → 仅 additive API + 已知 key 文案与现前端一致
