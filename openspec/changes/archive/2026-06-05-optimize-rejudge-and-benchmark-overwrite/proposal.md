# Proposal: 判据覆盖保存 + 重判优化（下拉选 judge / 只重判失败）

## Why

平台两处操作体验待优化：

1. **判据编辑只能"另存新集"**：用例明细的「编辑判据(YAML)」目前只能派生新 benchmark，无法直接覆盖回原集——用户改完判据想就地更新原 benchmark 时被迫产生一堆新集。
2. **重判换 judge 靠手填、且只能全量**：重判弹框换 judge 模型要手填 provider/model/base_url/api_key（与「发起评测」从判分模型库下拉选不一致、易错、泄漏 key）；且重判总是全量，无法只对"上线判定失败"的用例重判（全量会对已通过用例白跑一遍 LLM judge、徒增成本与时间）。

## What Changes

1. **判据覆盖保存**：用例明细 YAML 编辑 MUST 在「另存为新 benchmark」之外，支持「**覆盖当前 benchmark**」——覆盖的合并语义与另存**完全一致**（复制源集全部用例、按 `sample_id` 只合并判据字段、未匹配丢弃、零匹配报错），只是写回原集而非新建。内置 benchmark MUST 禁止覆盖。
2. **重判换 judge 改下拉**：重判弹框换 judge 模型 MUST 改为从「判分模型库」下拉选（与发起评测一致，服务端注入连接信息与 Key），MUST NOT 再手填。
3. **只重判上线失败用例**：重判 MUST 支持一个可选项「只重判上线判定失败（`release_passed=false`）的用例」（默认仍全量）。勾选后只对失败用例重放留痕重判，**通过用例沿用源 run 结果**，合并后 MUST 重算整体分数/通过率/分布。重判仍**产出新 run**（`parent_run_id` 指向源、源 run 不可变、可 diff）。

## Impact

- Affected specs: `eval-platform-dashboard`。
- Affected code：
  - `server/benchmarks.py`：新增 `overwrite_benchmark_from_yaml`（复用 `_apply_case_overrides` 合并语义、写回源集、内置拒绝）。
  - `server/routers/benchmarks.py`：新增 `POST /{id}/overwrite-yaml`。
  - `server/schemas.py`：`RejudgeRequest` 加 `judge_model_id` / `only_release_failed`；新增 `OverwriteBenchmarkYamlRequest`。
  - `server/routers/runs.py`：`rejudge_run` 解析 `judge_model_id`→judge 覆盖（复用 create_run 逻辑）、透传 `only_release_failed`；`only_release_failed` 但源无失败用例时 400。
  - `server/eval_job.py`：`build_rejudge_job` 支持 `only_release_failed`——只判失败子集 + 合并源报告通过用例 + `build_report` 重算。
  - `frontend/src/pages/CaseDetailPage.tsx` 或 `RunDashboardPage.tsx`（YAML 弹框所在处）：加「覆盖当前 benchmark」。
  - `frontend/src/pages/RunDashboardPage.tsx`：重判弹框 judge 下拉 + 「只重判上线失败」勾选。
  - `frontend/src/api.ts`：对应接口/类型。
- 判分内核 `medeval/` 仅复用既有 `judge_traces` / `build_report`，不改 `TestCase` / `BaseJudge` / `FailureTag`。
