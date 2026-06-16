# Tasks: P0 医疗打分口径收紧

## 1. 测试先行（TDD）

- [x] 1.1 `function_deduction` 默认 0.15；must_have 缺失扣 0.15
- [x] 1.2 `scoring_point.summary` 净分映射功能 ±0.15；无得分点不调整
- [x] 1.3 功能分不超过 `module_max.function`
- [x] 1.4 红旗用例 YAML 含 `must_have_all: true`（loader 校验或快照测试）
- [x] 1.5 症状/多轮用例含 `inquiry_completeness` rubric

## 2. 实现

- [x] 2.1 `scoring.py` + `config.yaml`：扣分步长、scoring_point 功能映射
- [x] 2.2 更新 `symptom.yaml` / `multi_turn.yaml` / 红旗相关 YAML
- [x] 2.3 同步 `openspec/specs/reporting` 与 `judging-pipeline` delta

## 3. 验证

- [x] 3.1 `pytest` 全绿
- [x] 3.2 `medeval validate` + `medeval run --dry-run`
- [x] 3.3 `graphify update` + `openspec validate --strict` + archive
