# Proposal: add-memory-recall-suite

## Why

现有 `multi_turn.yaml` 与 `adversarial.yaml` 已覆盖部分上下文一致性，但缺少按记忆题型（隐式综合/显式召回/干扰召回/信息更正/抗假记忆）系统组织的专集，难以单独观测 bot 的单 session 记忆召回能力。

## What

- 新增 `cases/breast_cancer/memory.yaml`，15 条记忆召回用例。
- `scenario` 统一为 `记忆召回`；题型与临床主题写入 `sub_scenario`（`<题型>·<主题>`）。
- 主判分以 `scoring_points` checklist 为主，`rubric.multi_turn_consistency` 兜底。
- 新增 `tests/test_memory_recall_suite.py`；更新 benchmark 计数测试（92 → 105，含与 multi_turn/adversarial 去重 2 题）。

## Scope

- **In**: `cases/breast_cancer/memory.yaml`、`tests/`、`cases/README.md`、breast-cancer-case-suite spec delta
- **Out**: Runner/Adapter 改动、跨 session 记忆、schema 扩展

## Success

- `load_cases` 加载 105 题无重复 `sample_id`（记忆专集与 `bc_mt_d5_followup_recall` / `bc_d6b_multiturn_contradiction` 去重后）。
- `pytest tests/test_memory_recall_suite.py tests/test_clinical_benchmark_migration.py` 通过。
- 五种 `sub_scenario` 题型前缀各至少 2 条。
