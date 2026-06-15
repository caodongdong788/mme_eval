# Proposal: 评测平台完整补齐落 trace + 离线重判/断点续跑 + 存储治理

## Why

内核已具备「推理产物落盘 + 离线重判 + 断点续跑 + 存储治理」（见已归档 change
`2026-06-04-persist-traces-rejudge`），但 Web 平台 `server/eval_job.py` 仍走旧调用：

- 平台发起的评测**不落 `traces.jsonl.gz`**，导致网页发起的 run 无法离线重判、无法断点续跑；
- 平台没有 retention 收尾，`outputs/` 胖产物（traces/xlsx）随网页评测无限累积；
- 用户在看板里改了判分口径只能**重新跑一遍 bot**（费钱、慢、且掺入 bot 抖动），无法"只重判"；
- 评测中断（超时/重启）后只能从零重跑。

这是上一轮刻意划定的非目标，现按用户要求**完整补齐到平台**，让 CLI 与 Web 能力对齐。

## What Changes

- **平台落 trace**：`build_eval_job` 提前生成 run_slug、向 `evaluate()` 传 `run_name/out_dir`，
  使网页发起的评测与 CLI 一样落 `traces.jsonl.gz`；落库时记录 `EvalRun.has_traces`。
- **断点续跑（平台）**：新增 `POST /api/runs/{id}/resume`——以源 run 的冻结用例 + 成功留痕
  续跑（adapter 指纹不一致则拒绝），产出**新 run**。
- **离线重判（平台）**：新增 `POST /api/runs/{id}/rejudge`——对源 run 的冻结用例 + 冻结留痕
  仅重跑判分（零 adapter 调用），产出**新 run**，默认与源 run 对比。
- **置顶保护**：新增 `POST /api/runs/{id}/pin`（toggle）——`EvalRun.pinned` 标记，并在产物目录
  落 `KEEP` 哨兵，使 CLI/平台 retention 都豁免该 run。
- **平台 retention 收尾**：评测任务完成后按 `config.run.retention` 自动清理历史胖产物
  （永久保留 `report.json` 与 DB 数据）。
- **DB 标记 + API 出参 + 前端按钮**：`EvalRun` 增 `has_traces/pinned/parent_run_id`（含轻量
  幂等迁移），`RunSummaryOut` 透出，前端 run 看板加「重判 / 续跑 / 置顶」操作。

## Impact

- Affected specs: `eval-platform-service`（落 trace、重判、续跑、置顶、retention、新 API、迁移）、
  `eval-platform-dashboard`（看板操作入口）。
- Affected code: `server/eval_job.py`、`server/jobs.py`(无改/复用)、`server/models_db.py`、
  `server/db.py`、`server/ingest.py`(置 has_traces)、`server/routers/runs.py`、`server/schemas.py`、
  `frontend/src/api.ts`、`frontend/src/pages/RunDashboardPage.tsx`。
- 判分内核 `medeval/**` **零改动**（仅复用其 `service.run_traces/judge_traces`、`trace_store`、
  `retention`、`run_slug`）。
- 非目标（保持不变，留待后续）：外置对象存储（S3 等）、平台级 retention 的可视化配置页、
  rejudge/resume 的进度合并展示优化。
