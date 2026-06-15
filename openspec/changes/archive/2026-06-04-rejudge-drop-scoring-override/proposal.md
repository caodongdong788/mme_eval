# Proposal: 重判去掉「调判分口径(权重/阈值)」覆盖

## Why

刚上线的重判弹框提供了「四模块满分权重 / 扣分步长」覆盖，但本项目的四模块满分权重是
**profile 自适应**的：每条 case 先按 `profile_match` 解析 profile（default / red_flag /
adversarial / knowledge / rehab），再用该 profile 的 `module_max` 打分。而弹框覆盖的是
**顶层 `config.scoring.module_max`**（= default profile + 各 profile 未覆盖维度的兜底基线）。
由于 `config.yaml` 里 4 个 profile 都把四维 `module_max` 写满、整组覆盖顶层，弹框改顶层权重
对 red_flag / adversarial / knowledge / rehab 的 case **不生效**，只动 default 那批——语义割裂、
易误导。结论：这层权重编辑在 profile 自适应口径下没有意义，移除。

换 judge 模型、改 case 判据派生新 benchmark 重判这两块**保留**（仍有意义）。

## What Changes

- **移除重判的 scoring 覆盖**：`POST /api/runs/{id}/rejudge` body 不再接收 `scoring`；
  重判弹框去掉四模块权重 / 扣分步长输入。重判仍可换 judge 模型、用 `cases_benchmark_id`
  替换冻结用例判据。
- 删除随之而来的无用代码：后端 `_apply_scoring_override`、`build_rejudge_job` 的
  `scoring_override` 形参、`RejudgeRequest.scoring`、前端 `RejudgePayload.scoring` 与弹框权重表单、
  相关测试。

## Impact

- Affected specs: `eval-platform-service`（重判覆盖项收窄）、`eval-platform-dashboard`（重判弹框收窄）。
- Affected code: `server/schemas.py`、`server/eval_job.py`、`server/routers/runs.py`、
  `frontend/src/api.ts`、`frontend/src/pages/RunDashboardPage.tsx`、`tests/server/test_rejudge_overrides.py`。
- 判分内核 `medeval/**` 零改动。
