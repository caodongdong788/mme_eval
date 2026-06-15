# Design: 合并去重为单一乳腺癌 benchmark

## 决策(用户已确认)

- 迁移范围:**全量保留**——老套件所有独有/安全关键内容补 `scoring_points` 后迁入。
- 目录形态:**拍平**到 `cases/breast_cancer/<病程类>.yaml`(去 `clinical_benchmark/` 嵌套)。
- `_core_safety/`:**一并删除**,只留乳腺癌 benchmark。

## 终态目录(单一套件)

```
cases/breast_cancer/
  prevention_screening.yaml   # y1–y5 (+迁入: BI-RADS 分级含义, 遗传咨询)
  symptom.yaml                # y6–y10
  pathology.yaml              # y11–y15
  treatment.yaml              # y16–y20
  rehab.yaml                  # y21–y25 (+迁入: 乳房重建, 确诊期焦虑共情, 内分泌骨健康)
  followup.yaml               # y26–y30 (+迁入: 肿瘤标志物解读)
  red_flags.yaml              # 新增: 6 道肿瘤急症红旗 (level L3, red_flag_triage)
  adversarial.yaml            # d1–d10 + d2b + d6b (+迁入: D1–D10 未覆盖的处方/过度诊断对抗)
  multi_turn.yaml             # mts1–mts8 (+迁入: 多轮红旗升级, 及 depth/场景缺口)
```

## 老套件 36 题 去重/迁移决策表

| 老 sample_id | 处置 | 去向 / 理由 |
|---|---|---|
| bc_rf_febrile_neutropenia | **迁移** | red_flags.yaml(粒缺发热急诊,新套件无) |
| bc_rf_cord_compression | **迁移** | red_flags.yaml(脊髓压迫急诊) |
| bc_rf_brain_mets | **迁移** | red_flags.yaml(脑转移高颅压) |
| bc_rf_svc_syndrome | **迁移** | red_flags.yaml(上腔静脉综合征) |
| bc_rf_inflammatory_bc | **迁移** | red_flags.yaml(炎性乳癌 required_referral) |
| bc_rf_hypercalcemia | **迁移** | red_flags.yaml(高钙危象) |
| bc_mt_d3_chemo_fever_escalate | **迁移** | multi_turn.yaml(多轮红旗升级,新 mts 无) |
| bc_surv_reconstruction | **迁移** | rehab.yaml(乳房重建,新套件无) |
| bc_psych_diagnosis_anxiety | **迁移** | rehab.yaml(确诊期焦虑/共情,新套件无) |
| bc_brca_basic + bc_genetic_family_history | **合并迁移** | prevention_screening.yaml(遗传咨询,合并为 1–2 题) |
| bc_fu_tumor_marker | **迁移** | followup.yaml(肿瘤标志物解读,y27 仅泛述项目) |
| bc_se_endocrine_bone | **迁移** | rehab.yaml(内分泌治疗骨健康/骨密度) |
| bc_birads_meaning | **迁移** | prevention_screening.yaml(BI-RADS 分级含义) |
| bc_adv_chemo_dose | **条件迁移** | 处方剂量边界(improper_prescription),若 D1–D10 未覆盖则迁入 adversarial.yaml |
| bc_adv_symptom_dx | **条件迁移** | 症状→确诊过度诊断,同上 |
| bc_adv_pathology_verdict | **条件迁移** | 越病理下恶性结论,同上 |
| bc_adv_stop_endocrine | **条件迁移** | 怂恿自停内分泌(单轮版),同上 |
| bc_mt_d2_screen_anxiety | **条件迁移** | 若需补 depth-2 / 筛查焦虑多轮缺口 |
| bc_mt_d3_pathology_staged | **条件迁移** | 若需补 depth-3 病理分阶段多轮缺口 |
| bc_mt_d4_stop_endocrine_pressure | **条件迁移** | 满足规格「多轮停药施压守恒」 |
| bc_mt_d5_followup_recall | **条件迁移** | 满足规格「depth-5 长程记忆一致性」 |
| bc_mammo_vs_us | 删 | = bc_y4_mammo_or_us_45 |
| bc_er_pr_her2 | 删 | ≈ bc_y14_her2_positive |
| bc_tnbc_def | 删 | ≈ bc_y15_tnbc_severity |
| bc_bcs_vs_mastectomy | 删 | = bc_y16 / bc_mts1 |
| bc_special_pregnancy | 删 | = bc_y20_pregnancy_bc |
| bc_path_report_read | 删 | ≈ bc_y11–y14 |
| bc_path_subtype_tnm | 删 | ≈ bc_y13 / y15 |
| bc_screen_start_age | 删 | ≈ bc_y4 |
| bc_screen_birds3 | 删 | ≈ bc_y12;BI-RADS 已由迁移题覆盖 |
| bc_se_chemo_common | 删 | ≈ bc_y24 |
| bc_fu_frequency | 删 | = bc_y26_followup_interval |
| bc_treat_chemo_vs_target | 删 | = bc_y17_targeted_vs_chemo |
| bc_treat_neoadjuvant | 删 | ≈ bc_mts3_tnbc_neoadjuvant |
| bc_adv_alt_therapy | 删 | ≈ d1/d3/d7(supplement/refuse/folk) |

> 「条件迁移」原则:实现者 MUST 读老题与现有新题正文比对,**仅当该题的具体边界/场景/depth 未被任何现有新题覆盖,或为 `breast-cancer-case-suite` 规格强制要求(depth 2–5、停药施压多轮守恒、depth-5 长程记忆、处方/过度诊断对抗)时才迁移**;否则按重复删除。医疗保守:存疑时倾向保留迁移。

## 迁移题质量要求

- 迁入题 MUST 复用现有 `TestCase` schema,`sample_id` 保留原 `bc_` id(全局唯一、保溯源)。
- MUST 补 `scoring_points`,引用具名指南锚点且**带版本年份**(对齐新套件风格,如「NCCN 2025 版」「CSCO BC 2024」)。
- MUST 按病程标注 taxonomy tag,使 `profile_match` 可解析 profile;红旗题保 `red_flag_triage` + `level: L3`(命中 `red_flag` profile),对抗题带 `adversarial` tag(命中 `adversarial` profile)。
- 红旗题 `failure_tags_candidates` MUST 含 `missed_red_flag`;对抗处方题含 `improper_prescription`、过度诊断含 `over_diagnosis`。

## 配置变更

`config.yaml`:
```yaml
cases:
  include:
    - "cases/breast_cancer"   # 唯一乳腺癌 benchmark(拍平)
```
更新 `run.description` 文案去掉「通用安全底座(6) + L1/L2/L3/L4(36)」表述,改为反映单一病程 taxonomy benchmark。

## 规格 delta 计划(`breast-cancer-case-suite`)

- MODIFY「专属红旗急症」:路径 `L3_red_flags/` → `cases/breast_cancer/red_flags.yaml`。
- MODIFY「专科对抗场景」:路径 `L4_adversarial/` → `adversarial.yaml`,并入 D1–D10 口径。
- MODIFY「多轮 depth 2-5」:路径 `multi_turn/` → `multi_turn.yaml`。
- MODIFY「8 阶段」requirement:去掉「与 139 条通用病例一起加载」陈旧 scenario,改为拍平病程 taxonomy。
- MODIFY「必须删除旧通用集...」:include 改为仅 `["cases/breast_cancer"]`,`_core_safety/` 亦删除。
- **REMOVE**「套件必须保留精简的跨科通用安全底座」(删 `_core_safety`)。

## 验收门

1. `.venv/bin/python -m pytest`(尤其 `tests/test_clinical_benchmark_migration.py`、loader、profile)全绿。
2. 加载 `cases/breast_cancer/` 无 `sample_id` 重复、无指向已删目录报错;6 红旗题解析为 `red_flag` profile、对抗题为 `adversarial`。
3. `cases/` 下仅余 `breast_cancer/`(无 `_core_safety/`、无 `L*`、无 `clinical_benchmark/`)。
4. `openspec validate consolidate-breast-cancer-benchmark --strict` 通过。
5. `graphify update .` 刷新;README/AGENTS 计数与结构一致(README 失败标签 AUTO-GENERATED 块不破坏)。

## 不做

- 不改判分逻辑 / 不触 `hard_gate.py`(无需 `verify-heuristics`),`fingerprint` 不变。
- 不动 `config.yaml` 里既有 api_key(已知问题,不在本 change 范围)。
