# Tasks: 合并去重为单一乳腺癌 benchmark

## 1. 迁移老套件独有 / 安全关键内容(删除前完成)
- [x] 1.1 新建 `cases/breast_cancer/red_flags.yaml`,迁入 6 道肿瘤急症红旗,补带版本指南锚点 `scoring_points`,保 `red_flag_triage`、加 `level: L3`、`failure_tags_candidates` 含 `missed_red_flag`
- [x] 1.2 迁入多轮红旗升级 `bc_mt_d3_chemo_fever_escalate` 到 `multi_turn.yaml`,补 `scoring_points` 与 `multi_turn_consistency` rubric
- [x] 1.3 迁入 rehab 类:乳房重建、确诊期焦虑共情、内分泌骨健康 → `rehab.yaml`(补 `scoring_points` + 病程 tag)
- [x] 1.4 迁入 prevention_screening 类:遗传咨询(合并 brca_basic+genetic_family_history)、BI-RADS 分级含义 → `prevention_screening.yaml`
- [x] 1.5 迁入 followup 类:肿瘤标志物解读 → `followup.yaml`
- [x] 1.6 逐条比对「条件迁移」对抗题(chemo_dose/symptom_dx/pathology_verdict/stop_endocrine)与老多轮(d2/d3/d4/d5):未被现有新题覆盖或规格强制者迁入并补 `scoring_points`,否则记为删除（结论:8 道条件迁移题全部迁入，均为规格强制覆盖项）

## 2. 拍平目录 + 去重删除
- [x] 2.1 将 `cases/breast_cancer/clinical_benchmark/*.yaml` 上移为 `cases/breast_cancer/<病程类>.yaml`(`d_adversarial→adversarial`、`mt_scenarios→multi_turn`、`y_*→对应病程类`),删除空的 `clinical_benchmark/`
- [x] 2.2 删除老 Level 目录:`L1_knowledge/` `L2_scenarios/` `L3_red_flags/` `L4_adversarial/` `multi_turn/`(独有内容已在第 1 节迁出)
- [x] 2.3 删除 `cases/_core_safety/`
- [x] 2.4 校验:`cases/` 下仅余 `breast_cancer/`,无重复 `sample_id`、无残留嵌套目录

## 3. 配置 / 文档同步
- [x] 3.1 `config.yaml`:`cases.include` 改为仅 `["cases/breast_cancer"]`,更新 `run.description`
- [x] 3.2 更新 README 结构与计数;`AGENTS.md` 用例库描述同步(保持 README 失败标签 `AUTO-GENERATED` 块完整)

## 4. 规格 delta(`specs/breast-cancer-case-suite/spec.md`)
- [x] 4.1 写 MODIFIED:红旗(路径→red_flags.yaml)、对抗(→adversarial.yaml,并入 D1–D10)、多轮(→multi_turn.yaml)、8 阶段(去 139 条陈旧 scenario)、删除旧集要求(include 仅 breast_cancer)
- [x] 4.2 写 REMOVED:「套件必须保留精简的跨科通用安全底座」(`_core_safety` 已删)
- [x] 4.3 `openspec validate consolidate-breast-cancer-benchmark --strict` 通过

## 5. 测试更新 + 验收
- [x] 5.1 更新 `tests/test_clinical_benchmark_migration.py`:`SUITE_DIR` 改为 `cases/breast_cancer`,计数/断言改为合并后实际值;新增红旗 profile 路由断言、`_core_safety` 已删断言
- [x] 5.2 `.venv/bin/python -m pytest` 全绿
- [x] 5.3 加载冒烟:`medeval validate` / `list-cases` 不报错,红旗题→`red_flag` profile、对抗题→`adversarial` profile

## 6. 收尾
- [x] 6.1 `graphify update .`
- [x] 6.2 `openspec archive consolidate-breast-cancer-benchmark`(归档前再次 validate)
