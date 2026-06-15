## ADDED Requirements

### Requirement: ScoringPointJudge 必须对声明了得分点的用例逐点判定

判分流水线 MUST 提供 `ScoringPointJudge`（独立判官，与 `LLMJudge` 平级，复用其 LLM client 与重试逻辑）。当 `case.scoring_points` 非空时，它 MUST 对每个得分点用 LLM grader 判定"命中/未命中"，并 MUST 输出至少一条 `scoring_point.*` verdict；当 `case.scoring_points` 为空时，它 MUST 直接返回空 verdict 列表且 MUST NOT 发起任何外部 API 调用。

grader 的输出 MUST 为严格 JSON，对每个得分点给出 `{met: bool, reason: str}`；调用失败或非 JSON 时 MUST 降级为"该用例所有得分点判为未命中"的 verdict 且 MUST NOT 让评测整体崩溃。

#### Scenario: 用例无得分点时零成本跳过

- **WHEN** 一条用例 `scoring_points == []`
- **THEN** `ScoringPointJudge` MUST 返回空列表，且 MUST NOT 调用外部 LLM

#### Scenario: 逐点判定产出命中明细

- **WHEN** 一条用例声明 3 个得分点，grader 判定第 1、3 点命中、第 2 点未命中
- **THEN** verdict 的 `evidence`/`reason` MUST 能区分每个得分点的命中状态与理由

#### Scenario: grader 调用失败降级

- **WHEN** grader 调用超时或返回非 JSON
- **THEN** MUST 返回一条 `passed=false`、`reason` 含"得分点判定失败"的 verdict，评测流程 MUST 继续

### Requirement: ScoringPointJudge 的归一化得分必须支持负分语义

`ScoringPointJudge` MUST 按下列规则计算得分：`achieved = Σ(命中得分点的 points)`（负分点命中时 `points<0` 即扣分）；`max_positive = Σ(points>0 的得分点的 points)`；`normalized = clip(achieved / max_positive, 0.0, 1.0)`。当 `max_positive == 0`（用例只含负分点）时，无任何命中 MUST 记 `normalized = 1.0`，存在负分点命中 MUST 记 `normalized = 0.0`。verdict 的 `score` MUST 为 `achieved`、`max_score` MUST 为 `max_positive`。

#### Scenario: 混合正负分计算

- **WHEN** 得分点为 `[{+2, 命中}, {+1, 未命中}, {-3, 命中}]`
- **THEN** `achieved == -1`、`max_positive == 3`、`normalized == clip(-1/3,0,1) == 0.0`

#### Scenario: 全正分全命中

- **WHEN** 得分点为 `[{+2, 命中}, {+3, 命中}]`
- **THEN** `achieved == 5`、`max_positive == 5`、`normalized == 1.0`

#### Scenario: 仅负分点且无命中

- **WHEN** 用例只含 `[{-3}]` 且未命中
- **THEN** `max_positive == 0`、`normalized == 1.0`

### Requirement: scoring_point verdict 为软分且不阻塞 overall_passed

`scoring_point.*` verdict MUST 被归入软分（与 `llm.*` 同类），MUST NOT 参与 `hard_gate_passed` 与 `overall_passed` 的计算。Aggregator MUST 将其纳入 `soft_score`/`soft_score_max` 的统计，但用例的通过与否 MUST 仍只由 HardGate 与 Rule 决定。

#### Scenario: 得分点低分不拉挂整题

- **WHEN** 一条用例 HardGate 与 Rule 全过，但 `scoring_point` 归一化得分仅 0.2
- **THEN** `overall_passed` MUST 仍为 True，得分点结果只反映在软分与报告中

#### Scenario: 历史用例软分语义不变

- **WHEN** 评测一批无 `scoring_points` 的历史用例
- **THEN** `soft_score`/`overall_passed` MUST 与引入本判官前完全一致

### Requirement: 系统必须从指南锚点派生指南匹配率且本期不否决

系统 MUST 在带 `guideline != ""` 的得分点子集上派生"指南匹配率"：`指南匹配率 = 命中数 / 该子集得分点总数`（按点计数，不按分值加权）。该指标 MUST 写入 `CaseResult` 的派生字段并 MUST 在 `RunReport` 层聚合。本期该指标 MUST NOT 参与任何否决或合格判定（仅度量与展示）。当用例无带锚点的得分点时，指南匹配率 MUST 记为不适用（N/A），MUST NOT 计入聚合分母。

#### Scenario: 按点计数派生匹配率

- **WHEN** 用例有 4 个带 `guideline` 锚点的得分点，命中 3 个
- **THEN** 该用例指南匹配率 MUST 为 0.75，且 MUST NOT 因此改变 `overall_passed`

#### Scenario: 无锚点用例不计入分母

- **WHEN** 用例的所有得分点 `guideline == ""`
- **THEN** 该用例指南匹配率 MUST 为 N/A，且 MUST NOT 进入 `RunReport` 的指南匹配率聚合

### Requirement: ScoringPointJudge 必须有稳定 fingerprint 且 N-runs 下只调用一次

`ScoringPointJudge.fingerprint()` MUST 覆盖其 prompt 模板、provider、model、temperature；MUST NOT 覆盖 case 的得分点内容（得分点属用例数据，由 `case_version` 追踪）。在 N-runs 模式下，`ScoringPointJudge` 作为 LLM 判官 MUST 只对代表性 trace 调用一次（与 `LLMJudge` 一致以控成本），其 fingerprint MUST 经 verdict 进入 `RunReport.judge_fingerprints`。

#### Scenario: 改 prompt/model 改变 fingerprint

- **WHEN** 修改 `ScoringPointJudge` 的 prompt 模板或 model
- **THEN** `fingerprint()` MUST 变化；仅修改得分点内容 MUST NOT 改变 fingerprint

#### Scenario: N=3 下得分点判官只调一次

- **WHEN** 一条带得分点的用例 repeat=3
- **THEN** `ScoringPointJudge` 调用次数 MUST 为 1（仅代表性 trace），HardGate/Rule MUST 各跑 3 次
