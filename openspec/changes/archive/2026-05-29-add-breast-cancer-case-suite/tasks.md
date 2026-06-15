## 1. 通用安全底座 (_core_safety)

- [x] 1.1 `cases/_core_safety/generic_red_flags.yaml`：3 条跨科红旗（心梗 / 卒中 / 过敏性休克），`core_` 前缀，`tags: [core_safety, red_flag]`，`red_flag_triage: required_emergency`
- [x] 1.2 `cases/_core_safety/generic_boundary.yaml`：3 条通用边界（越界处方诱导 + 免责漂移 + 诱导确诊），`tags: [core_safety, adversarial]`

## 2. 乳腺癌 L1 常识 (breast_cancer/L1_knowledge)

- [x] 2.1 `cases/breast_cancer/L1_knowledge/bc_basics.yaml`：6 条常识横跨阶段 —— BI-RADS 分级含义 / 钼靶 vs B超适用 / ER·PR·HER2 是什么 / 三阴性乳腺癌定义 / 保乳 vs 全切区别 / BRCA 基因是什么；全部 `bc_` 前缀、`factual_accuracy` 软分

## 3. 乳腺癌 L2 业务场景 (breast_cancer/L2_scenarios)

- [x] 3.1 `screening.yaml`：2 条 —— 一般风险女性何时开始钼靶筛查 / BI-RADS 3 类如何随访
- [x] 3.2 `pathology.yaml`：2 条 —— 病理报告 ER+/PR+/HER2- 解读 / 分子分型（Luminal·HER2+·TNBC）与 TNM 分期含义
- [x] 3.3 `treatment.yaml`：2 条 —— 化疗 vs 靶向区别 / 新辅助化疗目的与适应证科普（不给方案剂量）
- [x] 3.4 `side_effects.yaml`：2 条 —— 化疗脱发恶心口腔溃疡居家应对 / 内分泌治疗潮热与骨健康管理
- [x] 3.5 `followup.yaml`：2 条 —— 术后复查频率 / 肿瘤标志物意义（不夸大、不替代影像）
- [x] 3.6 `psych_survivorship.yaml`：2 条 —— 确诊焦虑情绪疏导（重 empathy）/ 形体重建·义乳·运动营养科普
- [x] 3.7 `genetic_special.yaml`：2 条 —— BRCA1/2 与家族史风险（引导遗传咨询）/ 特殊人群（妊娠期乳腺癌）

## 4. 乳腺癌 L3 红旗急症 (breast_cancer/L3_red_flags)

- [x] 4.1 `bc_oncology_emergencies.yaml`：6 条 —— 粒缺发热 / 骨转移脊髓压迫 / 脑转移高颅压 / 上腔静脉综合征 / 炎性乳腺癌(referral) / 高钙血症危象；全部含急诊 must_have + 危险安抚 must_not_have + `missed_red_flag` candidate；`notes` 写临床依据

## 5. 乳腺癌 L4 对抗 (breast_cancer/L4_adversarial)

- [x] 5.1 `bc_adversarial.yaml`：5 条 —— 诱导化疗剂量 / 背书偏方拒治 / 症状诱导确诊 / 替代病理下恶性结论 / 怂恿停内分泌治疗；failure_tags 取自现有词表

## 6. 乳腺癌多轮 (breast_cancer/multi_turn)

- [x] 6.1 `bc_multi_turn.yaml`：5 条覆盖 depth 2-5 —— d2 筛查焦虑+结节浮出 / d3 病理分段解读 / d3 化疗副作用→粒缺发热升级(红旗) / d4 内分泌副作用→停药施压(对抗) / d5 长程随访记忆；全部含 `multi_turn_consistency`

## 7. 删除旧集 + 配置调整

- [x] 7.1 删除旧用例目录：`cases/L1_medical_knowledge` / `cases/L2_scenarios` / `cases/L3_red_flags` / `cases/L4_adversarial` / `cases/multi_turn`（仓库非 git，直接 rm）
- [x] 7.2 重写 `config.yaml`：迁入 `config.multi_turn.yaml` 的完整设置（豆包 adapter + HardGate/Rule/GPT-5.1 judge + lark），`cases.include: [cases/_core_safety, cases/breast_cancer]`，`run.name` 含 `breast_cancer`，`diff_against` 留空（首份无基线）；LLM 密钥改走环境变量 `AIDP_API_KEY` 不落盘
- [x] 7.3 删除失效配置 `config.l1.yaml`、`config.multi_turn.yaml`

## 8. 校验

- [x] 8.1 加载 `cases/_core_safety` + `cases/breast_cancer`，确认 schema 校验通过、sample_id 全局唯一、总数 42（~40）；确认 `cases/` 下已无旧目录（`medeval validate` 通过）
- [x] 8.2 核对覆盖契约：8 阶段各 ≥1 条（screening/pathology/treatment/side_effects/followup/psych+survivorship/genetic/special_pop 全覆盖）、L3=10≥6 条急症、L4=8≥5 条对抗、多轮=5≥5 条含 depth5、底座=6≥5 条
- [x] 8.3 `openspec validate --strict add-breast-cancer-case-suite` 通过
- [ ] 8.4 （可选）`medeval run --config config.yaml` 端到端冒烟，确认报告与飞书 docx 正常 —— 留给用户触发（会真实调用豆包+GPT-5.1 并发布飞书）
