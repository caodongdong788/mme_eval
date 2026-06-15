# Proposal: 合并去重为单一乳腺癌 benchmark

## Why

当前 `cases/breast_cancer/` 下并存两套乳腺癌用例,造成冗余、重复计分与评估深度不一致:

1. **老套件(按 Level 分层,36 题)**:`L1_knowledge/` `L2_scenarios/` `L3_red_flags/` `L4_adversarial/` `multi_turn/`,无 `scoring_points`。
2. **新套件(按病程 taxonomy,50 题)**:`clinical_benchmark/`,从临床方案迁移,带版本化指南锚点 `scoring_points`。

两套在「保乳 vs 全切」「靶向 vs 化疗」「新辅助」「孕期乳腺癌」「BI-RADS」等话题大量重叠,导致同一能力被重复计分;而老套件独有且**安全关键**的内容(6 道肿瘤急症红旗、多轮红旗升级、确诊期共情、乳房重建、遗传咨询、肿瘤标志物解读、内分泌骨健康、BI-RADS 分级)在新套件中**完全缺失或覆盖薄弱**。同时 `cases/_core_safety/` 通用底座与本次「专科单一 benchmark」目标无关,需一并下线。

目标:**以新套件(病程 taxonomy + scoring_points)为唯一基准**,把老套件独有内容补 `scoring_points` 后迁入,去重删除重复题,删除老 Level 目录与 `_core_safety/`,拍平到 `cases/breast_cancer/<病程类>.yaml`,全仓库维护**一套**乳腺癌 benchmark。

## What Changes

- **拍平目录**:`cases/breast_cancer/clinical_benchmark/*.yaml` 上移为 `cases/breast_cancer/<病程类>.yaml`,去掉 `clinical_benchmark/` 嵌套。
- **新增红旗类**:新增 `cases/breast_cancer/red_flags.yaml`,迁入 6 道肿瘤急症红旗(化疗后粒缺发热、骨转移脊髓压迫、脑转移高颅压、上腔静脉综合征、炎性乳癌、高钙危象),补 `scoring_points`,保留 `red_flag_triage` 并标 `level: L3` 以命中 `red_flag` profile。
- **迁移老套件独有题**(补 `scoring_points` + 病程 tag):多轮红旗升级、乳房重建、确诊期焦虑共情、遗传咨询(合并 brca_basic+genetic_family_history)、肿瘤标志物解读、内分泌骨健康、BI-RADS 分级,以及 D1–D10 未覆盖的处方/过度诊断对抗边界。
- **去重删除**:与新套件话题重复的老题直接删。
- **删除老结构**:删 `cases/breast_cancer/L1_knowledge/` `L2_scenarios/` `L3_red_flags/` `L4_adversarial/` `multi_turn/` 与 `cases/_core_safety/`。
- **配置**:`config.yaml` 的 `cases.include` 改为仅 `["cases/breast_cancer"]`;更新 `run.description` 文案。
- **测试/文档/规格**:更新 `tests/test_clinical_benchmark_migration.py`(路径/计数/断言)、README、AGENTS.md;改写 `breast-cancer-case-suite` 规格(去掉 Level/`_core_safety` 依赖、改为拍平病程 taxonomy)。

## Impact

- Affected specs: `breast-cancer-case-suite`(MODIFIED 多条 + REMOVED `_core_safety` 要求),`case-schema-and-loader`(若引用旧路径)。
- Affected code/data: `cases/breast_cancer/**`、`cases/_core_safety/`(删)、`config.yaml`、`tests/test_clinical_benchmark_migration.py`、`README.md`、`AGENTS.md`。
- **不可逆删除**:老套件与 `_core_safety` 直接删除(用户已确认),删除前所有独有/安全关键内容 MUST 已迁入新套件。
- 不改判分逻辑、不触 `hard_gate.py`,故无需跑 `verify-heuristics`;`fingerprint` 不变。
