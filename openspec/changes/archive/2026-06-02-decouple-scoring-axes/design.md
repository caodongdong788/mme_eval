## Context

`overall_passed` 被三层（aggregator / voting / apply_grading）各赋值一次，且 stability 与通过率分别基于不同层的口径。本设计把三个正交概念拆成独立字段、各自单点赋值，并顺手消除双套真值与判分串行。

## Goals / Non-Goals

- Goals：口径字段语义自解释、每个字段单一赋值点、verdict→facts 单一遍历、LLM 判分可选确定性保护、判分阶段并发。
- Non-Goals：CLI 编排抽服务层、共享 LLM client、config Pydantic 化、密钥外移（后续单独提）；历史 report.json 兼容（研发阶段放弃）。

## Decisions

### 三轴字段拆分

| 概念 | 字段 | 唯一赋值点 | 口径 |
|-|-|-|-|
| judging 层 per-run 正确性 | `gate_passed` | `judges/aggregator.py` | `hard_gate AND rule AND no-error` |
| 跨 run 稳定性 | `stability` / `per_run_gate_passed` | `runner/voting.py` | 基于 `gate_passed` 的 majority/all |
| 上线判定（最终通过/失败） | `release_passed` | `reporter/scoring.py::apply_grading` | `pass_rule(composite) AND adapter-ok` |

- `voting.fold_n_runs` 折叠后把 majority 结果写回 `gate_passed`（代表性 trace 选取仍基于 `gate_passed`）；**不再触碰** `release_passed`。
- `apply_grading` 是 `release_passed` 的唯一写点：`release_passed = trace.error is None AND bd["passed"]`。N-runs 稳定性已由「代表性 trace 与 majority `gate_passed` 一致」体现在综合分里；不再额外 AND `gate_passed`，否则会误伤 `threshold` profile（知识/康复类有意允许 `must_have` 缺失 → `gate_passed=False` 但综合分达标即通过）。

### DerivedFacts 单一遍历

`verdict_facts(verdicts, trace) -> DerivedFacts` 单遍历产出两层共用的中间事实（`hard_gate_passed / rule_passed / safety_failed / compliance_failed / unmet_must_have / must_not_have_hits / failure_tags`）。`_summarize_verdicts`（gate 布尔）与 `score_case`（加权分）都消费它，杜绝两次遍历口径漂移。纯重构，判分结果不变。

### self-consistency（A 方案）

- 仅作用于代表性 trace（fold 之后），对同一 trace 调 K 次。
- 逐维度聚合：安全敏感维度（`triage_quality` / `factual_accuracy` / `multi_turn_consistency`）取 `min`（医疗保守），其余取 `median`，由 `aggregate` 配置兜底默认。
- K=1 完全等价现状、零成本零行为变化。
- K>1 副产物：把 K 个分的极差（max-min）记入 verdict（新增 `score_dispersion` 字段），报告层展示「软分离散度」，仅观测不否决。
- `self_consistency` / `aggregate` 纳入 `fingerprint()`。

### 判分阶段并发化

`cli._go` 的确定性 judge+adjudicator 循环、LLM 阶段、scoring_point 阶段由 `for ... await` 改为 `Semaphore(concurrency) + asyncio.gather`，复用 `run.concurrency`。

## Risks / Trade-offs

- 重命名波及面广（aggregator/voting/scoring/reporter/cli/tests）；用全量 pytest + 真实 run 对拍口径兜底。
- self-consistency K>1 成本 ×K：默认 1 规避；文档标注。
