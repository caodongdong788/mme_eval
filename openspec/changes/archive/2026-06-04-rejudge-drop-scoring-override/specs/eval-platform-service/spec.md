# eval-platform-service Specification (delta)

## MODIFIED Requirements

### Requirement: 重判可带配置覆盖

`POST /api/runs/{run_id}/rejudge` SHALL 接收可选 body，允许对本次重判临时覆盖判分相关配置，
而 MUST NOT 修改服务器 `config.yaml`：

- `judge`：合并进 `config.judges.llm/scoring_point`（provider/model/base_url/api_key），
  重判用新判分模型重跑 LLM judge；`api_key` MUST NOT 入库；
- `cases_benchmark_id`：用该 benchmark 的用例判据按 `sample_id` 替换源 run 的冻结用例，
  trace 仍冻结，重跑判分。

覆盖仅作用于本次重判产出的新 run；bot 会话留痕始终冻结。无 body 时行为与既有重判一致。
`cases_benchmark_id` 指向不存在的 benchmark MUST 返回 400。系统 MUST NOT 提供对四模块满分权重
/ 阈值（`scoring`）的重判覆盖（权重为 profile 自适应，顶层覆盖语义割裂，故不暴露）。

#### Scenario: 换 judge 模型重判

- **WHEN** 用户对某 run 重判并传入 `judge` 覆盖（如新的 model）
- **THEN** 新 run 用该 judge 模型重跑判分，且服务器 `config.yaml` MUST 保持不变

#### Scenario: 用改后判据重判

- **WHEN** 用户重判并传入 `cases_benchmark_id` 指向一个改了判据的 benchmark
- **THEN** 系统按 `sample_id` 用该 benchmark 的用例判据替换冻结用例后重跑判分，bot 回答不变
