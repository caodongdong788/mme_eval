# Tasks

## 阶段1：类别自适应权重 + 分级合格阈值
- [x] 1.1 `scoring.py` 加 `resolve_profile(case, scoring_cfg)`：按 `profile_match` 解析类别 → 返回 profile（module_max/grade_thresholds/pass_rule）
- [x] 1.2 `score_case` 支持传入解析后的 profile（沿用现有四模块打分），breakdown 增 `profile` 名
- [x] 1.3 `apply_grading` 按 profile.pass_rule（perfect / threshold+gates）判 `overall_passed`；`CaseResult.score_profile` 持久化
- [x] 1.4 `config.yaml` 增 `scoring.profiles` + `profile_match`（red_flag/adversarial/knowledge/rehab + 解析顺序）
- [x] 1.5 测试：`tests/test_category_profiles.py`（默认行为不变 + 权重自适应 + threshold/gates + 多轮/红旗/tag 解析）全绿
- [x] 1.6 报告展示每题所用 profile（Excel/markdown 增列或标注）

## 阶段2：指南要点库样板
- [x] 2.1 选 2–3 道（知识/治疗类）把「标准答案依据」拆成带 guideline 锚点的 scoring_points
- [x] 2.2 跑通 ScoringPointJudge + 指南匹配率，确认报告体现
- [x] 2.3 给出样板模板供后续批量迁移复用（技术在全量迁移中复用）

## 阶段3：对抗性套件 D1–D10
- [x] 3.1 建 `cases/breast_cancer/clinical_benchmark/d_adversarial.yaml`，统一 tag=adversarial（命中 adversarial profile）
- [x] 3.2 迁移 D1–D10，补 D2b 危机沟通(自伤意念) / D6b 多轮上下文自相矛盾探针
- [x] 3.3 验证 adversarial profile 生效（安全重权 + perfect，见 test_clinical_benchmark_migration）

## 阶段4：全量内容迁移
- [x] 4.1 30 单轮迁移，病程 6 类 tag + expected_behavior/hard_gates/rubric/scoring_points
- [x] 4.2 8 多轮迁移，背景卡 + 多轮一致性 rubric
- [x] 4.3 覆盖矩阵自检（test_clinical_benchmark_migration：30+8+12 计数与 profile 路由）

## 阶段5：人审校准 + 指南版本化
- [x] 5.1 校准集目录 + 一致性度量脚本（不进 CI gate）
- [x] 5.2 指南锚点版本写入 scoring_points.guideline，确认随 snapshot/fingerprint 落盘

## 收尾
- [x] 6.1 写 spec delta（reporting / judging-pipeline / breast-cancer-case-suite）
- [x] 6.2 跑全量测试 + 全量 case 回归
- [x] 6.3 `openspec validate` 通过并归档
