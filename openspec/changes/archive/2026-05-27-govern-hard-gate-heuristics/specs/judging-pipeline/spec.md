## 新增需求

### 需求:HardGate 关键词表必须附带结构化块注释

`HardGateJudge` 中的每一个 module-level 词表 / 正则常量（含 `_EMERGENCY_PATTERNS`、`_REFERRAL_PATTERNS`、`_DOSAGE_PATTERN`、`_FREQ_PATTERN`、`_DIETARY_CONTEXT_WORDS`、`_DRUG_CONTEXT_WORDS`、`_DIAGNOSIS_PHRASES`、`_DISCLAIMER_PATTERNS`）必须在其声明上方放置 5 行结构化注释，按以下顺序提供字段：

- `# Purpose:` ── ≤80 字描述这张表用于识别什么
- `# Added:` ── 引入日期 + 当时的 HardGateJudge fingerprint（依赖 add-judge-fingerprint 变更）
- `# Source:` ── 临床来源（指南 / 论文 / 真实日志 / 红队）
- `# Reviewed-by:` ── 飞书 ID 或显式 `TBD-clinician` 占位
- `# Golden-tests:` ── 该表对应的黄金集 anchor，必须能指向至少一条 yaml 用例

任一字段缺失或顺序错误必须由 lint 脚本 `scripts/check_heuristics_comments.py` 检测并使 PR 失败。

#### 场景:词表上方注释完整

- **当** `_EMERGENCY_PATTERNS` 上方有完整 5 行结构化注释
- **那么** `scripts/check_heuristics_comments.py` 检查通过

#### 场景:缺失任一字段必须 lint fail

- **当** 开发者新增 `_NEW_PATTERN = [...]` 但忘记加 `# Source:` 行
- **那么** lint 必须报错，错误消息必须指明常量名与缺失字段名

#### 场景:Reviewed-by 为 TBD 时必须警告不阻塞

- **当** 某张表的 `Reviewed-by:` 为 `TBD-clinician`
- **那么** CI 必须输出黄色警告"建议尽快指派临床 owner"，但不阻止合入

### 需求:HardGate 必须有黄金集回归测试保护关键词修改

仓库必须维护两份黄金集 YAML：`tests/golden/hard_gate_should_pass.yaml` 与 `tests/golden/hard_gate_should_fail.yaml`，每份至少 30 条用例片段，覆盖红旗触发 / 处方边界 / 免责声明三道门槛。每条 golden 用例必须由 ≥2 人交叉 review 后入库（PR description 中显式记录 reviewer），且必须由 Pydantic schema 校验。

`tests/test_hard_gate_golden.py` 必须基于黄金集构造 `ConversationTrace` 直接调 `HardGateJudge.judge`，断言每条用例的实际 verdict 与 `expected.*` 一致；对 should_fail 集还必须比对 `expected_failure_tags` 是实际产生标签的子集。该测试必须接入 CI 主流程，任何修改 HardGate 关键词表的 PR 必须使其全绿才能合入。

#### 场景:修改 _EMERGENCY_PATTERNS 让黄金通过用例失败

- **当** 开发者删除 `_EMERGENCY_PATTERNS` 中的"拨打 120"正则
- **那么** `tests/test_hard_gate_golden.py` 中所有依赖该模式的 should_pass 用例必须 fail，CI 必须阻止合入

#### 场景:should_fail 用例的标签子集语义

- **当** 黄金集声明 `expected_failure_tags: [missed_red_flag]`，实际产生 `[missed_red_flag, under_referral]`
- **那么** 测试必须通过（实际是 expected 的超集）

#### 场景:should_pass 用例必须三道门全过

- **当** 一条 should_pass 用例的 `expected.no_prescription=pass` 但 HardGate 实际报 fail
- **那么** 该用例必须 fail，且测试输出必须含 user_input 摘录与差异详情

### 需求:HardGate 关键词修改必须随附 CHANGELOG 条目

仓库必须维护 `medeval/judges/heuristics/CHANGELOG.md`，按版本号倒序记录每次关键词表变动。每个版本条目必须包含：版本号、HardGateJudge fingerprint（依赖 add-judge-fingerprint 变更）、日期、`Reviewed-by`、修改内容摘要、触发原因（如某条用例漏报）、黄金集影响。

修改 `hard_gate.py` 中关键词表的 PR 若没有同步更新 CHANGELOG.md，必须由 CI 脚本 `scripts/check_heuristics_changelog.py` 检测并阻止合入。

#### 场景:关键词改动 + CHANGELOG 同步更新

- **当** 一个 PR 在 `_DRUG_CONTEXT_WORDS` 中新增"维 C 泡腾片"，且在 CHANGELOG.md 顶部新增一段含 fingerprint / 修改原因
- **那么** CI 必须通过

#### 场景:关键词改动但 CHANGELOG 未更新

- **当** 一个 PR 修改了 `_DRUG_CONTEXT_WORDS` 但未触动 CHANGELOG.md
- **那么** `scripts/check_heuristics_changelog.py` 必须 fail，提示"修改了 hard_gate 关键词表但 CHANGELOG.md 未更新"

#### 场景:仅修改 hard_gate.py 中的注释或逻辑代码（非关键词表）

- **当** 一个 PR 修改了 `_check_red_flag` 函数逻辑但未触动任一关键词常量
- **那么** CHANGELOG 检查可以放行（关键词表保持不变）
