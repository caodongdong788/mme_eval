# Proposal: 结构化 Output Check（确定性 Code Grader）

## Why

三层 Grader 里 Code Grader 这一层最弱：现在只有 `rule.py` 的关键词级 must_have/must_not_have，
缺"结构化输出"的确定性断言（长度上限、必含结构段、禁止格式、JSON 合法性/字段齐全）。这类检查
零 LLM 成本、可批量回归、不受判官波动影响，是补齐 Code 层、给"频繁迭代"兜底的最快一环。

## What Changes

- **Schema**：`ExpectedBehavior` 新增 `output_checks: list[OutputCheck]`（默认空）。`OutputCheck`
  含受控 `kind` + `params` + 可选 `note`。首批 `kind`：`max_chars` / `min_chars` /
  `must_contain` / `forbid_regex` / `json_valid` / `required_fields`（后两者面向未来结构化 agent，
  现库自由文本用前四者）。
- **判定（确定性、零 API）**：`RuleJudge` 新增逐条 Output Check 校验，每条产出
  `rule.output_check{i}` verdict；失败 emit `FailureTag.CONSTRAINT_VIOLATION`。空 `output_checks`
  返回零 verdict（存量用例零行为变化）。
- **计分接入**：`reporter/scoring.py` 功能模块对每条失败的 output_check 从功能满分起扣
  `function_deduction`（与 must_not_have 命中同口径），进 `release_passed` 判定。
- **fingerprint**：Output Check 校验逻辑源码纳入 `RuleJudge.fingerprint()`，使"判分逻辑变化"
  可被 diff 区分。

## Impact

- Affected specs: `judging-pipeline`（结构化 Output Check）、`case-schema-and-loader`（OutputCheck schema）
- Affected code: `medeval/models.py`（`OutputCheck` 模型，触及 `TestCase`/`ExpectedBehavior` 核心节点）、
  `medeval/judges/rule.py`、`medeval/reporter/scoring.py`
- 不动 `hard_gate.py`（无需 `verify-heuristics`）；不新增 pip 依赖（JSON 用标准库）；
  空 `output_checks` 对全部存量用例零行为变化。
