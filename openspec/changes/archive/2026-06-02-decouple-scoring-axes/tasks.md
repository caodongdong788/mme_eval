## 1. DerivedFacts 单一遍历（纯重构）

- [x] 1.1 `judges/aggregator.py` 新增 `DerivedFacts` dataclass + `verdict_facts(verdicts, trace) -> DerivedFacts`
- [x] 1.2 `_summarize_verdicts` 改为消费 `verdict_facts`
- [x] 1.3 `reporter/scoring.py::score_case` 的 safety/compliance/function 解释改为消费 `verdict_facts`（判分结果不变）

## 2. 拆字段并收敛单一赋值点

- [x] 2.1 `models.py` `CaseResult`：`overall_passed`→`release_passed`、新增 `gate_passed`、`per_run_passed`→`per_run_gate_passed`；`JudgeVerdict` 新增 `score_dispersion`
- [x] 2.2 `judges/aggregator.py`：`judge_all` / `recompute_result_summary` 只写 `gate_passed`
- [x] 2.3 `runner/voting.py`：majority / stability / 逐 run 记录全部基于 `gate_passed`，写回 `gate_passed`，字段用 `per_run_gate_passed`
- [x] 2.4 `reporter/scoring.py::apply_grading`：唯一写 `release_passed = trace.error is None and bd["passed"] and gate_passed`

## 3. 下游引用切换

- [x] 3.1 `reporter/aggregator.py`：`report.passed` / `_bump` / 注释切到 `release_passed`
- [x] 3.2 `reporter/markdown_report.py`：`_failure_section` / `failed_n` / `_stability_prefix` 切到 `release_passed` / `per_run_gate_passed`
- [x] 3.3 `reporter/diff.py`：regression/improvement 读 `release_passed`
- [x] 3.4 `reporter/excel_transcript.py`：概览 `passed` 列读 `release_passed`
- [x] 3.5 `cli.py::_check_thresholds`：基于 `release_passed` 的 `report.passed`

## 4. LLM/得分点 self-consistency + 离散度

- [x] 4.1 `config.yaml` `judges.llm` / `judges.scoring_point` 增 `self_consistency: 1` 与 `aggregate`
- [x] 4.2 `judges/llm.py`：K>1 时对代表 trace 调 K 次，逐维度 min/median 聚合，记 `score_dispersion`；`fingerprint` 纳入新参数
- [x] 4.3 `judges/scoring_point.py`：同步 self_consistency（聚合归一化得分）
- [x] 4.4 `reporter/markdown_report.py`：新增软分离散度概览行（仅观测、不否决）

## 5. 判分阶段并发化

- [x] 5.1 `cli.py::_go`：确定性 judge+adjudicator、LLM、scoring_point 三处由串行改 `Semaphore + asyncio.gather`

## 6. 测试与知识库

- [x] 6.1 更新 `tests/`：voting / aggregator / scoring / diff 相关用例切到新字段名与口径
- [x] 6.2 全量 `pytest` 通过；`medeval verify-heuristics` 回归
- [x] 6.3 `AGENTS.md` / `README.md` 更新三轴口径说明（`gate_passed` / `release_passed` / stability）
- [x] 6.4 `graphify update .` 刷新图谱
