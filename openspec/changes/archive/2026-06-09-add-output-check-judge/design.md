# Design: 结构化 Output Check

## 受控 kind（v1）

| kind | params | 判定（对 bot 完整回复文本） |
|------|--------|------------------------------|
| `max_chars` | `{max: int}` | `len(reply) <= max` 通过 |
| `min_chars` | `{min: int}` | `len(reply) >= min` 通过 |
| `must_contain` | `{pattern: str, regex: bool=false}` | 含子串 / 正则命中即通过 |
| `forbid_regex` | `{pattern: str}` | 正则**未**命中即通过 |
| `json_valid` | `{}` | 回复整体可 `json.loads` 即通过 |
| `required_fields` | `{fields: [str]}` | 回复是 JSON 对象且含全部顶层字段即通过（隐含 json_valid） |

> `json_schema`（完整 schema 校验）本期不做——需引入 `jsonschema` 依赖且现库无结构化输出；
> 留待未来结构化 agent 用例再加，先用 `required_fields` 覆盖"字段齐全"的最常见诉求。

## 判定与计分

- `RuleJudge.judge` 在 must_have/must_not_have 之后追加逐条 Output Check：每条产出
  `rule.output_check{i}` verdict（`passed` + ≤40 字 `reason`），失败附
  `FailureTag.CONSTRAINT_VIOLATION`。`output_checks` 为空 → 不产出任何 verdict。
- `reporter/scoring.py` 功能模块在 must_not_have 之后扫描 `rule.output_check*` verdict，
  每条失败 `function -= function_deduction`，并记一条"功能 -x：输出检查未过「…」"。

## 约束

- **确定性 / 零 API**：纯文本/JSON 解析，不调 LLM。
- **存量零行为变化**：无 `output_checks` 声明 = 不产 verdict = 不扣分。
- **fingerprint**：`_eval_output_check` 源码纳入 `RuleJudge.fingerprint()`。
- **不进 gate**：失败只走功能扣分（影响 `release_passed`），不写 `hard_gate.*`/`gate_passed`。
