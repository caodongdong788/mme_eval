# Proposal: 续跑可恢复被中断的 run + 列表指南匹配率带计数

## Why

1. **被服务重启中断的 run 无法续跑（核心缺口）**：进程重启 / 热重载 / 崩溃后，孤儿任务回收会把 `running/pending` 的 run 置为 `failed`，但该 run **从未写出 `report.json`**（report.json 仅在整轮判分结束后才落）。而 `POST /api/runs/{id}/resume` 当前**硬性要求 `report.json` 存在**，于是这种"跑到一半被打断"的 run——恰恰是最该续跑、已烧掉大量 token 的场景——只能删除，无法续跑。底层 `traces.partial.jsonl`（每条完成即 flush）其实就躺在目录里、`trace_store.read_traces` 也支持回退读 partial，缺口纯粹在平台这道闸门 + 用例集重建逻辑。

   附带问题：现有闸门用 `report.json` 判定"可续跑"是**错的方向**——retention 会清理 `traces.jsonl.gz` 但永久保留 `report.json`，于是被清理过留痕的 run 反而通过闸门、却在任务里因无留痕而失败。

2. **用例列表指南匹配率只有百分比、没有具体命中数**：用例详情已是 `X%（命中/总数）`，但列表新增的「指南匹配率」列只显示 `X%`，对照不直观。需在百分比后补 `xx/xx`。

## What Changes

1. **续跑闸门放宽 + 用例集重建**：
   - `POST /api/runs/{id}/resume` 的可续跑判据从"`report.json` 存在"改为"**存在可复用留痕**（`traces.jsonl.gz` 或 `traces.partial.jsonl`）"；二者皆无时返回 400；无 `report.json` 且 run 未关联 benchmark 时返回 400（无法重建用例集）。
   - 评测启动时落一份 `plan.json`（`{sample_ids, n_runs}`，捕获**过滤后**的实际用例集），使中断后仍可精确重建意图用例集（含 levels/limit 过滤）。
   - `build_resume_job` 在源 run 无 `report.json` 时，从源 run 的 benchmark 重建用例集（按 `plan.json` 的 sample_ids 过滤 / 排序，无 plan 时回退全量 benchmark），再用 partial 留痕续跑；有 `report.json` 时行为不变。

2. **列表指南匹配率带计数**：`CaseRowOut` 新增 `guideline_matched` / `guideline_total`（服务端从已落 `detail_json` 派生，零迁移、对历史 run 同样生效），前端列表渲染为 `X%（命中/总数）`，无锚点显示「无锚点」。

## Impact

- Affected specs: `eval-platform-service`（续跑要求 MODIFIED）、`eval-platform-dashboard`（列表指南匹配率计数 ADDED）
- Affected code: `server/eval_job.py`（plan.json 读写 + 续跑用例集重建）、`server/routers/runs.py`（resume 闸门 + 列表派生计数）、`server/schemas.py`（CaseRowOut 字段）、`frontend/src/api.ts` + `frontend/src/pages/RunDashboardPage.tsx`（列表渲染）
- 无 DB 迁移：`plan.json` 是 run 目录内文件；指南计数从 `detail_json` 即时派生。
- 不触及判分内核 / HardGate / 核心节点（`TestCase`/`BaseJudge`/`FailureTag`），无 `verify-heuristics` 风险。
