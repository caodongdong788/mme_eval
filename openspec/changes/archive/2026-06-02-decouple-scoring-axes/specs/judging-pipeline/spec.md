## MODIFIED Requirements

### 需求:Aggregator 必须把多 Judge 输出合并为统一 CaseResult

`judge_all(case, trace, judges)` MUST 并行运行所有 judge（asyncio.gather），把 verdicts 拼到一起，并 MUST 通过单一的 `verdict_facts(verdicts, trace) -> DerivedFacts` 遍历派生中间事实（避免判分层与报告层各自重复遍历 verdict 导致口径漂移）。据此计算结论：

1. `hard_gate_passed` = 所有以 `hard_gate.` 开头的 verdict 都 passed（若无硬门槛则视为 True）
2. `gate_passed` = `hard_gate_passed` AND 所有以 `rule.` 开头的 verdict 都 passed AND `trace.error is None`（judging 层 per-run 正确性口径，用于 N-runs voting / stability）。这是 `gate_passed` 字段的**唯一赋值点**；报告层 MUST NOT 覆写它。最终报告的通过/失败由报告层 `release_passed` 决定（详见 reporting 规格），二者口径不同。
3. `soft_score` / `soft_score_max` 累加自所有 `llm.` 开头的 verdict
4. `failure_tags` = 所有 verdict 的 `failure_tags` 去重排序集合，其每个元素必须是 `FailureTag` 中某个成员的 `value`；若 `trace.error` 非空必须额外追加 `FailureTag.ADAPTER_ERROR.value`

`CaseResult` MUST NOT 再有名为 `overall_passed` 的 judging 层字段（已更名为 `gate_passed`）；judging 层只写 `gate_passed`。

#### 场景:trace 出错时 gate_passed 必须为 False

- **当** Runner 给出的 `trace.error` 非空（adapter 三次都超时）
- **那么** 不管硬门槛如何，`gate_passed` 必须为 False，failure_tags 必须包含 `"adapter_error"`（来自 `FailureTag.ADAPTER_ERROR`）

#### 场景:单个 judge crash 不能拖垮其他 judge

- **当** RuleJudge 由于 bug 抛出未捕获异常
- **那么** Aggregator 必须把它包装成一条 `rule.error` 的 fail verdict，HardGate 与 LLMJudge 的结果必须照常出齐

#### 场景:无硬门槛、无规则、纯软分用例

- **当** 用例只声明 rubric（如纯共情评测），未声明 hard_gates 与 expected_behavior
- **那么** `hard_gate_passed` 必须为 True，`gate_passed` 也为 True（不被软分拉低），soft_score 反映 LLMJudge 的分数

#### 场景:verdict→facts 单一遍历

- **当** 同一组 verdicts 既要派生 judging 层 `gate_passed`、又要在报告层算四模块加权分
- **那么** 两处 MUST 消费同一个 `verdict_facts(...)` 的 `DerivedFacts`，MUST NOT 各自重新 `verdict_by_name.get(...)` 遍历

### 需求:系统必须支持 N-runs majority voting 折叠

系统 MUST 提供 `fold_n_runs(per_run_results: list[list[CaseResult]]) -> list[CaseResult]`：把每条 case 的 N 次 `CaseResult` 折叠为单个最终 `CaseResult`。判定规则 MUST 为基于 `gate_passed` 的 **majority pass**：N 次中 `gate_passed=True` 的次数严格过半时（N 奇数 ≥⌈N/2⌉、N 偶数 >N/2）最终 `gate_passed=True`，否则 `False`。N=1 时直接返回原 result（不进入折叠路径）。majority/ stability MUST NOT 使用报告层的 `release_passed` 口径。

折叠后的最终 `CaseResult` MUST 新增/维护字段：

- `stability: Literal["stable_pass","flaky","stable_fail"]`
  - `stable_pass`：N 次 `gate_passed` 都是 True
  - `stable_fail`：N 次都是 False
  - `flaky`：N 次中既有 True 也有 False
- `n_runs: int = N`
- `per_run_gate_passed: list[bool]`：长度等于 N，按调用顺序记录每次的 `gate_passed`

折叠后 MUST 把 majority 结果写回 `gate_passed`；MUST NOT 触碰 `release_passed`（由报告层赋值）。`verdicts` 字段 MUST 保留"代表性 trace"对应那一次的完整 verdict 列表。代表性 trace 选取：在 N 次中筛选 `gate_passed` 与最终结果一致的子集，取最早一次（i 最小）。

#### 场景:N=3 majority 判定为 pass

- **当** 一条 case 跑 3 次，`per_run_gate_passed = [True, True, False]`
- **那么** 最终 `gate_passed` 必须为 True；`stability` 必须为 `flaky`；`verdicts` 必须取自第 0 次（最早的 pass run）

#### 场景:N=3 全失败

- **当** `per_run_gate_passed = [False, False, False]`
- **那么** 最终 `gate_passed` 为 False；`stability` 为 `stable_fail`

#### 场景:N=4 偶数平票算挂

- **当** N=4，`per_run_gate_passed = [True, True, False, False]`
- **那么** 最终 `gate_passed` 必须为 False（严格过半未达成）；`stability` 为 `flaky`

#### 场景:N=1 时不进入折叠路径

- **当** `repeat=1`
- **那么** 最终 `CaseResult` 必须满足 `n_runs=1`、`stability=stable_pass`（若 gate_passed）或 `stable_fail`（若否）、`per_run_gate_passed=[gate_passed]`；不得出现 `flaky`

## ADDED Requirements

### Requirement: LLM/得分点判官必须支持 self-consistency 多采样与离散度产出

`LLMJudge` 与 `ScoringPointJudge` MUST 支持可配置的 `self_consistency: int`（默认 1）与 `aggregate`（`min` / `median`）。当 `self_consistency == 1` 时，行为 MUST 与未引入本能力前完全一致（零额外成本、零行为变化）。当 `self_consistency = K > 1` 时，判官 MUST 对**同一代表性 trace** 调用 K 次，并按维度聚合 K 个分数：医疗安全敏感维度 MUST 取 `min`（保守），其余维度按 `aggregate` 配置（默认 `median`）。

K>1 时，判官 MUST 把该维度 K 个分数的离散度（极差 max-min）写入对应 verdict 的 `score_dispersion` 字段（默认 0.0）；该离散度 MUST 仅作观测与展示，MUST NOT 参与任何否决、合格或通过判定。`self_consistency` 与 `aggregate` MUST 纳入判官 `fingerprint()`。

#### Scenario: K=1 时零行为变化

- **WHEN** `judges.llm.self_consistency` 缺省或为 1
- **THEN** LLMJudge MUST 仅调用一次 LLM，verdict 的 `score_dispersion` MUST 为 0.0，判分结果与未引入本能力前一致

#### Scenario: K>1 时按维度聚合并记录离散度

- **WHEN** `self_consistency = 3`，某维度 3 次采样得分为 `[3, 4, 3]`、`aggregate = median`
- **THEN** 该维度 verdict 的 `score` MUST 为 3（median），`score_dispersion` MUST 为 1.0（max-min）

#### Scenario: 安全敏感维度取 min

- **WHEN** `self_consistency = 3`，`triage_quality` 三次采样得分为 `[2, 1, 2]`
- **THEN** 该维度 verdict 的 `score` MUST 为 1（min，医疗保守），与 `aggregate` 配置无关

#### Scenario: self_consistency 纳入 fingerprint

- **WHEN** 构造两个 `LLMJudge`，一个 `self_consistency=1`、一个 `self_consistency=3`，其余参数相同
- **THEN** 两者 `fingerprint()` MUST 不同
