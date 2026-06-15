# Tasks: LLM 判官 emit 受控 FailureTag

## 1. 测试先行（TDD）

- [x] 1.1 `empathy` 维度低分（score < max/2）→ `llm.empathy` verdict 含 `EMPATHY_MISS`
- [x] 1.2 `differential_thinking`/`factual_accuracy`/`multi_turn_consistency`/`inquiry_completeness`
      低分各 emit 对应 tag
- [x] 1.3 过线维度（score ≥ max/2）MUST NOT emit 标签
- [x] 1.4 `triage_quality` 低分 MUST NOT emit 标签（归 HardGate）
- [x] 1.5 LLMJudge 未启用 / 调用失败 → 不产出脏标签
- [x] 1.6 emit 标签不改变 `score`/`passed` 之外的轴；标签经 `reporter/aggregator` 进分布
- [x] 1.7 fingerprint：增/改维度→标签映射后 `LLMJudge.fingerprint()` 改变

## 2. 实现

- [x] 2.1 `medeval/judges/llm.py` 加 `_DIM_FAILURE_TAG` 映射常量
- [x] 2.2 构造维度 verdict 时，`passed=False` 则 append 对应 tag（self_consistency 与失败分支同样处理）
- [x] 2.3 `fingerprint()` 纳入 `_DIM_FAILURE_TAG`

## 3. 治理与文档

- [x] 3.1 `medeval/models.py` 去掉被激活 4 个标签的 `_RESERVED_NOTE` 后缀（INQUIRY_INCOMPLETE 本就已 emit）
- [x] 3.2 `python -m medeval.docs.gen_failure_tags --write` 刷新 README，并过 `--check`
- [x] 3.3 指纹漂移登记：`test_judge_fingerprint.py` 的 `llm_default` 快照更新（未触 HardGate，不入 heuristics-changelog）

## 4. 验证

- [x] 4.1 `pytest`（含 golden + failure_tags README 守门）全绿（587 passed）
- [x] 4.2 `openspec validate llm-judge-emit-failure-tags --strict`
- [x] 4.3 `graphify update .`
- [x] 4.4 归档
