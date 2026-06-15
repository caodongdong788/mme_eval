## Why

当前评测集（139 条）面向**通用全科**医疗 chatbot：L1 通用医学常识、L2 跨科业务场景、L3 全科急症红旗、L4 通用对抗、40 条多轮。但我们实际要评测的 agent 深耕**乳腺癌**方向。通用集无法考察乳腺癌专科能力（病理分型解读、治疗方案边界、肿瘤急症识别、内分泌/靶向副作用管理等），把它当 baseline 会严重高估或漏判 agent 在主战场上的真实表现。

需要一套**以乳腺癌为主体**的评测集：既覆盖乳腺癌患者完整旅程（筛查→诊断病理→治疗→副作用→随访复发→心理生存期→遗传高危→特殊人群），又保留一个精简的跨科安全底座（防止 agent 只会乳腺癌、丢掉通用红旗/拒处方/免责的基本盘）。

## What Changes

- **删除现有 139 条通用病例**：移除 `cases/L1_medical_knowledge/`、`cases/L2_scenarios/`、`cases/L3_red_flags/`、`cases/L4_adversarial/`、`cases/multi_turn/` 全部旧目录（不再保留，后续按需慢慢补充乳腺癌专科）
- 新增 `cases/breast_cancer/` 乳腺癌专科评测套件，按 L1-L4 + 多轮分层，覆盖 8 个旅程阶段，**首批种子 ~34 条**（验证方向后再扩量）
- 新增 `cases/_core_safety/` 精简通用安全底座 **~6 条**（跨科红旗 + 通用越界/免责，全部**新写**），保证 agent 不因专科化而丢失通用安全能力
- **处理失效 config**：旧 `config.yaml` / `config.l1.yaml` / `config.multi_turn.yaml` 均指向被删目录。将 `config.yaml` 重指向新套件并升级为完整判分设置（HardGate+Rule+LLM+lark），作为乳腺癌评测主配置；删除已无意义的 `config.l1.yaml` 与 `config.multi_turn.yaml`
- 复用现有 `FailureTag` 受控词表与 `Population` / `Rubric` 枚举，**不改 schema / 不改判分代码**（纯用例内容 + 配置调整）

## Capabilities

### New Capabilities
- `breast-cancer-case-suite`: 定义乳腺癌评测套件的**覆盖契约**——必须覆盖哪些旅程阶段、哪些乳腺癌专属红旗急症、哪些专科对抗场景，以及分层安全底座的最小保留集。这是套件的"验收标准"，与具体 YAML 内容解耦。

### Modified Capabilities
（无。`case-schema-and-loader` / `judging-pipeline` 的 schema 与判分语义均不变，本 change 只新增符合现有 schema 的用例内容与一份新 config。）

## Impact

- **新增用例文件**（约 40 条）
  - `cases/_core_safety/generic_red_flags.yaml`（~3-4 条非乳腺癌红旗）
  - `cases/_core_safety/generic_boundary.yaml`（~2-3 条通用越界/免责）
  - `cases/breast_cancer/L1_knowledge/bc_basics.yaml`（~6 条乳腺癌常识）
  - `cases/breast_cancer/L2_scenarios/*.yaml`（筛查/病理/治疗/副作用/随访/心理生存/遗传特殊，~14 条）
  - `cases/breast_cancer/L3_red_flags/bc_oncology_emergencies.yaml`（~6 条乳腺癌相关急症）
  - `cases/breast_cancer/L4_adversarial/bc_adversarial.yaml`（~5 条乳腺癌对抗）
  - `cases/breast_cancer/multi_turn/bc_multi_turn.yaml`（~5 条乳腺癌多轮）
- **删除文件**：`cases/L1_medical_knowledge/`、`cases/L2_scenarios/`、`cases/L3_red_flags/`、`cases/L4_adversarial/`、`cases/multi_turn/`（139 条旧用例）；`config.l1.yaml`、`config.multi_turn.yaml`（失效配置）
- **配置调整**：`config.yaml` 重指向 `[cases/_core_safety, cases/breast_cancer]` 并迁入完整判分/适配器/飞书设置，`run.name` 含 `breast_cancer_seed`
- **不改**：`medeval/` 任何代码、`openspec/specs/case-schema-and-loader`、`FailureTag` 词表、judges
- **依赖**：无新增
- **验证**：`load_cases` 能加载全部新用例（schema 校验通过、sample_id 唯一）；可选起一次 `medeval run --config config.yaml` 出报告确认端到端
- **后续**：种子验证方向 OK 后，再慢慢补充各阶段用例扩到全量
- **历史报告 / 归档**：`outputs/` 下旧通用集报告不动（历史留档）；旧 `outputs/doubao_multi_turn_*` 报告引用的 sample_id 已不在用例库，但报告本身是快照，不受影响
