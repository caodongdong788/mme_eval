# Tasks: 结构化 Output Check

## 1. 测试先行（TDD）

- [x] 1.1 `max_chars`/`min_chars` 边界：超限失败、达标通过
- [x] 1.2 `must_contain`（子串与 regex 两式）命中/未命中
- [x] 1.3 `forbid_regex` 命中即失败、未命中通过
- [x] 1.4 `json_valid` 合法/非法；`required_fields` 缺字段失败、齐全通过
- [x] 1.5 空 `output_checks` → RuleJudge 不产出 `rule.output_check*` verdict（零行为变化）
- [x] 1.6 失败的 output_check verdict 含 `FailureTag.CONSTRAINT_VIOLATION`
- [x] 1.7 计分：每条失败 output_check 让功能模块扣 `function_deduction`，进 `release_passed`
- [x] 1.8 fingerprint：引入 Output Check 逻辑后 `RuleJudge.fingerprint()` 改变（快照更新）

## 2. 实现

- [x] 2.1 `medeval/models.py`：`OutputCheckKind` 枚举 + `OutputCheck` 模型；`ExpectedBehavior.output_checks`
- [x] 2.2 `medeval/judges/rule.py`：`_eval_output_check` + `_check_output_checks`，judge 追加其 verdict
- [x] 2.3 `RuleJudge.fingerprint()` 纳入 `_eval_output_check` 源码
- [x] 2.4 `medeval/reporter/scoring.py`：功能模块扫描 `rule.output_check*` 逐条扣分

## 3. 验证

- [x] 3.1 `pytest`（含 golden）全绿（597 passed）
- [x] 3.2 `medeval run --config config.yaml --dry-run` 装配无误（71 用例）
- [x] 3.3 `openspec validate add-output-check-judge --strict`
- [x] 3.4 `graphify update .`
- [x] 3.5 归档
