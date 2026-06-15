## ADDED Requirements

### Requirement: Pairwise 对比发起 API

平台 SHALL 提供 `POST /api/compare/pairwise`，入参两个 run id（A 基线 / B 本次）与裁判
模型（取自判分模型库）。校验通过后 MUST 异步发起逐题 PK，立即返回一个
`PairwiseComparison` 记录（`status=running`）。后台任务 MUST 对两 run 共有的
`sample_id` 逐题调用 `PairwiseComparator` 并落库，收尾计算汇总并置 `status=done`；
执行异常 MUST 置 `status=failed` 且不影响既有评测数据。

#### Scenario: 合法发起返回 running 记录
- **WHEN** 用户对同 benchmark、判分尺子一致的两个 run 发起 pairwise
- **THEN** 返回 `status=running` 的比较记录 id，后台开始逐题判定

#### Scenario: 启动回收孤儿比较任务
- **WHEN** 服务重启后存在 `status=running` 且超时的比较记录
- **THEN** 平台启动时 MUST 将其回收为 `failed`

### Requirement: Pairwise 可比性校验

平台 SHALL 在发起前做可比性校验，**只卡判分尺子、放开被测 bot**。两个 run MUST 满足：
①`benchmark_id` 相同；②`sample_id` 集合完全一致；③判分尺子一致（`judge_fingerprints`
相等且 `config_snapshot.scoring` 相等）；④双方均已落 trace（`has_traces`）。任一不满足
MUST 拒绝（HTTP 422）并返回中文原因。被测参数（system_prompt / 被测 model）的差异
MUST NOT 拦截，而是计算为 `subject_diff` 随结果返回。

#### Scenario: 判分尺子不一致被拒
- **WHEN** 两个 run 的 `judge_fingerprints` 不同
- **THEN** 平台 MUST 返回 422 并提示「判分尺子不同，结果不可比」

#### Scenario: 被测 prompt 不同允许对比
- **WHEN** 两个 run 仅 `system_prompt` 不同，其余尺子一致
- **THEN** 平台 MUST 允许发起，并在结果中以 `subject_diff` 标明该差异

#### Scenario: 缺 trace 被拒
- **WHEN** 任一 run 未落 trace
- **THEN** 平台 MUST 拒绝并提示缺少留痕无法对比

### Requirement: Pairwise 结果查询 API

平台 SHALL 提供 `GET /api/compare/pairwise/{id}`，返回整体总结（胜/平/负计数、低置信
计数、按安全/功能/体验维度的胜率、回退用例清单、`subject_diff`）与逐用例列表（每条含
`sample_id`、`winner`、`confidence`、`dimension_winners`、`reason`）。结果 MUST 自落库
读取，不重新调用裁判。

#### Scenario: 返回总结与逐用例
- **WHEN** 比较 `status=done` 后查询结果
- **THEN** 返回整体胜率与维度胜率，以及可逐题查看的对比列表

### Requirement: Pairwise 数据建模与迁移

平台 SHALL 新增 `PairwiseComparison`（run_a_id/run_b_id/judge_model/judge_fingerprint/
status/汇总 JSON/created_by/created_at）与 `PairwiseCaseVerdict`（comparison_id/
sample_id/winner/confidence/dimension_winners/reason/swap_consistent）两表，并以轻量
幂等迁移（`CREATE TABLE IF NOT EXISTS` 同款）在启动时建表，MUST NOT 破坏既有数据。

#### Scenario: 启动幂等建表
- **WHEN** 服务启动且新表不存在
- **THEN** 平台 MUST 自动创建两张新表，已存在时跳过且不报错
