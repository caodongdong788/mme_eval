# Proposal: YAML 在线改判据 → 另存新 benchmark（解耦）+ 重判选集

## Why

现状"改 case 判据"在用例详情页**逐条结构化编辑、且每改一条就自动派生新 benchmark 并立即重判**——
即使只动一条用例也会生成一个新集 + 触发重判，耦合过重、不可批量、不够直观。

新设计把"编辑/派生 benchmark"和"重判"**解耦**，并用更贴近作者习惯的 **YAML 在线编辑**：
按看板当前过滤命中的用例子集打开完整 YAML，在线改判据 → 可选另存为新 benchmark（不触发重判）→
之后在重判对话框里**选某个 benchmark** 按其判据重判（复用既有 `cases_benchmark_id`，trace 冻结）。

## What Changes

- **看板按过滤子集在线编辑判据**：看板「用例结果」区新增「编辑判据(YAML)」抽屉，预填当前过滤命中用例的
  完整 YAML。保存时按 `sample_id` **只把判据字段**（`expected_behavior`/`hard_gates`/`rubric`/
  `scoring_points`）覆盖回源用例（`turns` 等不动）；YAML 中 `sample_id` 在源集找不到的**直接丢弃**；
  源集中未出现的用例保持原样；一条都没匹配则报错。校验通过后**另存为新的 uploaded benchmark**
  （不触发重判，不动源集）。
- **重判对话框选集重判**：重判弹框新增 benchmark 下拉，选中即以该集判据 `cases_benchmark_id` 重判
  （默认空＝沿用源 run 原判据）；judge 模型覆盖保留。
- **移除**用例详情页"逐条结构化编辑 + 自动派生重判"旧入口。
- 后端新增 `POST /api/benchmarks/{id}/derive-yaml` 与 `GET /api/runs/{id}/cases-yaml`（按 `/cases`
  过滤参数导出命中用例的完整 YAML 供预填）；`_apply_case_overrides` 未匹配语义由"报错"改为"跳过"。

## Impact

- Affected specs: `eval-platform-service`、`eval-platform-dashboard`。
- Affected code: `server/benchmarks.py`、`server/routers/benchmarks.py`、`server/routers/runs.py`、
  `server/schemas.py`、`frontend/src/api.ts`、`frontend/src/pages/RunDashboardPage.tsx`、
  `frontend/src/pages/CaseDetailPage.tsx`、`tests/server/test_rejudge_overrides.py`。
- 判分内核 `medeval/**` 零改动。结构化 `POST /benchmarks/{id}/derive` 端点后端保留备用（不再被前端使用）。
- 非目标：YAML 语法高亮（用等宽 textarea，不引入 Monaco）；YAML 里改 `turns` 等非判据字段（按设计忽略）。
