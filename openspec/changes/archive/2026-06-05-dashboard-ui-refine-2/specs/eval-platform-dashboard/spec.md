# eval-platform-dashboard Specification (delta)

## ADDED Requirements

### Requirement: 用例明细对话轮数

用例明细 MUST 展示每条用例的对话轮数，并 MUST 提供按轮数过滤（单轮 / 多轮），该过滤可与其它筛选叠加并随筛选条件记忆。
后端 `GET /api/runs/{run_id}/cases` MUST 在每行返回 `n_turns`（由已落库 `detail_json` 推导，单轮=1、多轮>1），
并 MUST 支持 `turns=single|multi` 过滤参数。该能力 MUST NOT 新增数据库列或改判分内核。

#### Scenario: 展示并按轮数过滤

- **WHEN** 用户在用例明细选择「对话轮数=多轮」
- **THEN** 列表 MUST 只显示对话轮数大于 1 的用例，且每行 MUST 展示其轮数

### Requirement: 用例详情中文映射

用例详情页 MUST 对枚举/标识类值做中文映射展示：评分档（profile）、稳定性（stability）、维度分与扣分原因的维度
key（safety/compliance/function/experience）、Judge 列的 judge key（`hard_gate.*` / `rule.*` / `llm.*` / `scoring_point.*`）。
未知值 MUST 安全回退为原始字符串，且映射 MUST NOT 改变后端数据或判分。

#### Scenario: 详情页中文呈现

- **WHEN** 用户打开某用例详情
- **THEN** 评分档/稳定性/维度 key/Judge key MUST 以中文呈现（未知值回退原文）

## MODIFIED Requirements

### Requirement: 单次评测看板

前端 SHALL 为单次 run 呈现聚合看板：核心指标卡（综合分/通过率/硬门槛失败/稳定性/待审）、四模块平均分、
分层级的用例数量与通过率（组合图）、失败标签分布（饼图）、延迟与成本（MUST 并排同一行展示），以及与上一次 run 的 diff。
看板内容 MUST 以「概览 / 用例明细」标签页组织；用例明细 MUST 含对话轮数列与轮数过滤。名称下方 meta MUST 精简为
judge 模型与 N（repeat 次数）两项。

#### Scenario: 查看单次评测看板

- **WHEN** 用户打开某次 run 的看板
- **THEN** 概览 MUST 展示上述聚合指标与图表，且延迟与成本 MUST 在同一行并排，用例明细 MUST 提供轮数列与轮数过滤
