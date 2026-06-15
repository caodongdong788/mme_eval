# judging-pipeline (delta)

## ADDED Requirements

### Requirement: LLMJudge 必须在维度失败时 emit 受控 FailureTag

`LLMJudge` MUST 在某 rubric 维度 verdict `passed=False`（即 `score < max/2`）时，于该 `llm.<dim>`
verdict 的 `failure_tags` 上 append 一个受控 `FailureTag`，按固定映射：

- `empathy` → `EMPATHY_MISS`
- `differential_thinking` → `DIFFERENTIAL_NARROW`
- `factual_accuracy` → `MEDICAL_HALLUCINATION`
- `multi_turn_consistency` → `DIALOG_BREAK`
- `inquiry_completeness` → `INQUIRY_INCOMPLETE`

`triage_quality` MUST NOT 映射任何标签（分诊归 HardGate，避免双重归因）。过线维度
（`score ≥ max/2`）、LLMJudge 未启用、judge 调用失败的降级 verdict MUST NOT emit 标签。

emit 的标签 MUST 为纯失败归因：MUST NOT 改变 `score` / `gate_passed` / `release_passed`，
仅经既有报告聚合流入看板失败分布。该维度→标签映射 MUST 纳入 `LLMJudge.fingerprint()`。

#### Scenario: 共情维度低分 emit EMPATHY_MISS

- **WHEN** LLMJudge 给 `empathy` 打分低于其满分的一半
- **THEN** `llm.empathy` verdict 的 `failure_tags` MUST 含 `EMPATHY_MISS`

#### Scenario: 过线维度不 emit 标签

- **WHEN** LLMJudge 给 `factual_accuracy` 打分达到或超过满分一半
- **THEN** 该 verdict 的 `failure_tags` MUST 为空

#### Scenario: 分诊维度不归 LLM 标签

- **WHEN** LLMJudge 给 `triage_quality` 打了低分
- **THEN** 该 verdict MUST NOT emit 任何 `FailureTag`（分诊失败归 HardGate）

#### Scenario: 未启用不产出脏标签

- **WHEN** LLMJudge `enabled=false` 或调用失败走降级分支
- **THEN** 任何 `llm.<dim>` verdict MUST NOT 含 `FailureTag`
