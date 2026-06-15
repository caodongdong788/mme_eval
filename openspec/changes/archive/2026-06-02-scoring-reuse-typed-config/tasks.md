# Tasks

## 1. 重构 scoring.py
- [x] 1.1 新增 `_as_scoring_cfg`（边界 `ScoringCfg.model_validate`）+ `_pass_rule_to_dict`（typed→归一 dict）
- [x] 1.2 `resolve_profile` 改读 typed 属性；`_when_matches` 改吃 `WhenCfg`；删除 `_normalize_pass_rule`
- [x] 1.3 保持 `resolve_profile` 返回 shape 与 `score_case`/`_evaluate_pass`/`apply_grading`/`grading_summary` 签名不变

## 2. 测试
- [x] 2.1 新增 `tests/test_scoring_typed_parsing.py`：snapshot dump dict 与等价 dict 一致、ScoringCfg 实例直接消费、pass_rule 三写法归一、未知键 / threshold 缺 min_composite fail-fast
- [x] 2.2 现有 `test_category_profiles`(/weighted_grading/clinical_benchmark_migration) 行为对拍（49 passed 不变）

## 3. 验证
- [x] 3.1 全量 `pytest` 绿（300 passed）
- [x] 3.2 `medeval verify-heuristics` 通过
- [x] 3.3 真实 config `medeval run --dry-run` 通过
- [x] 3.4 `graphify update .` 刷新图谱
- [x] 3.5 `openspec validate --strict` 通过并归档
