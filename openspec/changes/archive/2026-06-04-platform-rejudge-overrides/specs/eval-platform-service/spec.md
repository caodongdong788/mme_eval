# eval-platform-service Specification (delta)

## ADDED Requirements

### Requirement: 重判可带配置覆盖

`POST /api/runs/{run_id}/rejudge` SHALL 接收可选 body，允许对本次重判临时覆盖判分配置，
而 MUST NOT 修改服务器 `config.yaml`：

- `scoring`：浅合并进 `config.scoring`（四模块 `module_max` / `grade_thresholds` /
  `function_deduction` / `pass_rule`），重判按新口径重算评分；
- `judge`：合并进 `config.judges.llm/scoring_point`（provider/model/base_url/api_key），
  重判用新判分模型重跑 LLM judge；`api_key` MUST NOT 入库；
- `cases_benchmark_id`：用该 benchmark 的用例判据按 `sample_id` 替换源 run 的冻结用例，
  trace 仍冻结，重跑判分。

覆盖仅作用于本次重判产出的新 run；bot 会话留痕始终冻结。无 body 时行为与既有重判一致。
`cases_benchmark_id` 指向不存在的 benchmark MUST 返回 400。

#### Scenario: 调权重重判改变评分

- **WHEN** 用户对某 run 重判并传入 `scoring.module_max` 覆盖
- **THEN** 新 run 的综合分按覆盖后的权重重算，且服务器 `config.yaml` MUST 保持不变

#### Scenario: 用改后判据重判

- **WHEN** 用户重判并传入 `cases_benchmark_id` 指向一个改了判据的 benchmark
- **THEN** 系统按 `sample_id` 用该 benchmark 的用例判据替换冻结用例后重跑判分，bot 回答不变

### Requirement: 改 case 判据派生新 benchmark

系统 SHALL 提供 `POST /api/benchmarks/{benchmark_id}/derive`：复制源 benchmark 的全部用例，
按 `sample_id` 套用 `expected_behavior` / `hard_gates` / `rubric` 覆盖，逐条经 `TestCase`
schema 校验（非法 MUST 拒绝并返回错误），通过后**另存为一个新的 uploaded benchmark**。
该操作 MUST NOT 修改源 benchmark（含内置用例集），新 benchmark MUST 记录 `created_by` 为
当前登录用户。

#### Scenario: 派生不影响源 benchmark

- **WHEN** 用户基于某 benchmark 改若干用例判据并派生
- **THEN** 系统创建一个含改后判据的新 benchmark，源 benchmark 的用例 MUST 保持原样

#### Scenario: 非法判据被拒绝

- **WHEN** 派生请求中某条用例覆盖不符合 `TestCase` schema
- **THEN** 系统 MUST 拒绝派生并返回可读的校验错误

### Requirement: benchmark 记录并展示上传人

系统 SHALL 在上传或派生 benchmark 时把当前登录用户写入 `Benchmark.created_by`，并通过
`BenchmarkOut` 透出该字段；未登录（dev 放行）时 created_by 可为空。

#### Scenario: 上传人随 benchmark 落库并返回

- **WHEN** 已登录用户上传或派生一个 benchmark
- **THEN** 该 benchmark 的 `created_by` 记录其身份，列表/详情 API MUST 返回该字段
