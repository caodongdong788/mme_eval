## ADDED Requirements

### Requirement: 系统必须支持 N-runs majority voting 折叠

系统 MUST 提供 `fold_n_runs(per_run_results: list[list[CaseResult]], n: int) -> list[CaseResult]`：把每条 case 的 N 次 `CaseResult` 折叠为单个最终 `CaseResult`。判定规则 MUST 为 **majority pass**：N 次中 `overall_passed=True` 的次数严格过半时（即 N 奇数时 ≥⌈N/2⌉、N 偶数时 >N/2）最终 `overall_passed=True`，否则 `False`。N=1 时直接返回原 result（不进入折叠路径）。

折叠后的最终 `CaseResult` MUST 新增字段：
- `stability: Literal["stable_pass","flaky","stable_fail"]`
  - `stable_pass`：N 次 `overall_passed` 都是 True
  - `stable_fail`：N 次都是 False
  - `flaky`：N 次中既有 True 也有 False（无论 majority 怎么判）
- `n_runs: int = N`
- `per_run_passed: list[bool]`：长度等于 N，按调用顺序记录每次的 `overall_passed`

折叠后的最终 `CaseResult` 的 `verdicts` 字段 MUST 保留"代表性 trace"对应那一次的完整 verdict 列表（包括 LLM Judge 的 reason / score）。代表性 trace 选取规则：在 N 次中筛选 `overall_passed` 与最终结果一致的子集，再在子集中取最早一次（i 最小）。

#### 场景: N=3 majority 判定为 pass

- **WHEN** 一条 case 跑 3 次，`per_run_passed = [True, True, False]`
- **THEN** 最终 `overall_passed` 必须为 True；`stability` 必须为 `flaky`（不是 stable_pass，因为有抖动）；`verdicts` 必须取自第 0 次（最早的 pass run）

#### 场景: N=3 全失败

- **WHEN** `per_run_passed = [False, False, False]`
- **THEN** 最终 `overall_passed` 为 False；`stability` 为 `stable_fail`；`verdicts` 取自第 0 次

#### 场景: N=4 偶数平票算挂

- **WHEN** N=4，`per_run_passed = [True, True, False, False]`
- **THEN** 最终 `overall_passed` 必须为 False（严格过半未达成）；`stability` 为 `flaky`

#### 场景: N=1 时不进入折叠路径

- **WHEN** `repeat=1`
- **THEN** `fold_n_runs` 不得被调用，或被调用时直接 passthrough；最终 `CaseResult` 必须满足 `n_runs=1`、`stability=stable_pass`（若 passed）或 `stable_fail`（若 failed）、`per_run_passed=[overall_passed]`；不得出现 `flaky`

### Requirement: LLM Judge 在 N-runs 模式下只对代表性 trace 调用一次

为控制成本，LLM Judge MUST 不对 N 次中的每一次 trace 都重复打分。系统 MUST 在 `fold_n_runs` 之前，先对每次 trace 跑确定性 judge（HardGate + Rule，它们对相同 trace 一定输出相同 verdict、对不同 trace 可能输出不同 verdict），算出每次的 per-run `overall_passed`。然后在 majority 判定确定后，**只对代表性 trace** 跑一次 LLM Judge，把 LLM verdict 注入最终 `CaseResult.verdicts`。

代表性 trace 的"verdict 配置匹配"规则：选与最终结果一致的最早一次（i 最小）。

#### 场景: N=3 LLM Judge 调用次数

- **WHEN** 一条 case repeat=3 且 LLM Judge 启用
- **THEN** LLM Judge 调用次数必须为 1（不是 3）；HardGate / Rule 调用次数必须为 3（每次 trace 各跑一次）

#### 场景: N=3 但 LLM Judge 未启用

- **WHEN** 一条 case repeat=3 且 `judges.llm.enabled=false`
- **THEN** 整个判分链必须只执行 HardGate + Rule 各 3 次，整体 verdict 数 = 3 × (per-trace verdict 数)；折叠后 `CaseResult.verdicts` 字段必须取自代表性 trace 的那一次
