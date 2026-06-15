## 为什么

`HardGateJudge` 是医疗评测的"生死线"——红旗症状分诊、处方边界、免责声明三道硬门槛任一失败用例就视为 fail。其判断完全建立在 8 张内嵌词表/正则上（`_EMERGENCY_PATTERNS` / `_DRUG_CONTEXT_WORDS` / `_DIETARY_CONTEXT_WORDS` 等）。源码顶部只有一行注释提示"⚠️ 关键词列表是 P0 启发式，必须由医学专家在上线前 review"，但实际没有任何配套机制：

- 谁来 review？什么时候触发？没有定义。
- 一条关键词改动会让哪些历史用例的结论翻转？没有任何自动化能告知。
- 新增一个药物语境词（如把"维 C 泡腾片"加入药品列表）需要什么样的证据？没有标准。
- `outputs/doubao_baseline_v2/report.json` 的 description 写着"判 v2：修复假阳性处方 + 红旗 regex 放宽"——这次改动到底改了什么？只能靠 git log 复盘。

随着用例规模扩大、临床专家加入 review、CI 卡发版，这种"裸代码"的判分逻辑会成为治理黑洞。

## 变更内容

本提案采用 **A + B 组合**（注释规范 + 黄金集回归），不引入 yaml 外置（话题 3 方案 C 留到 P2）：

- **新增** 关键词表块的注释规范：每个词表/正则上方必须有 `# Purpose / # Added / # Source / # Reviewed-by / # Golden-tests` 五行结构化注释。
- **新增** 黄金集（Golden Set）：`tests/golden/hard_gate_should_pass.yaml` 与 `tests/golden/hard_gate_should_fail.yaml`，存放至少各 30 条已审核的用例片段（user input + expected HardGate verdict）。
- **新增** pytest 用例 `tests/test_hard_gate_golden.py` 在 CI 上跑通整张黄金集，任何修改关键词表的 PR 若让 golden 失败就阻止合入。
- **新增** `heuristics/CHANGELOG.md`（位于 `medeval/judges/heuristics/CHANGELOG.md`），按 fingerprint 版本号记录每次关键词改动的"什么 + 为什么 + 谁审"。
- **新增** 引用 `add-judge-fingerprint` 变更产生的 HardGate fingerprint，在 CHANGELOG 中标注每个版本对应哪个 fingerprint。

## 功能 (Capabilities)

### 新增功能

无（不引入新 capability）。

### 修改功能

- `judging-pipeline`: 引入关键词表的注释规范与黄金集回归保护，把"必须由临床专家 review"的口头要求具体化为 PR 可执行流程。
- `evaluation-cli`: 新增 `medeval verify-heuristics` 子命令，把注释 lint / 黄金集 / CHANGELOG 三检合一，便于开发者在 push 前快速本地验证。

## 影响

- **代码**: `medeval/judges/hard_gate.py` 在词表块上补注释（无逻辑变更）；新建 `medeval/judges/heuristics/CHANGELOG.md`。
- **测试**: 新增 `tests/golden/*.yaml` 与 `tests/test_hard_gate_golden.py`。
- **CI**: 必须把 `pytest tests/test_hard_gate_golden.py` 加入主流程；若与 `add-judge-fingerprint` 合并发布，CHANGELOG 必须随每次 fingerprint 改动更新。
- **依赖**: 无新增依赖（pytest 已在 `dev` extras）。
- **协作**: 引入"临床 owner"概念（CODEOWNERS 或 CHANGELOG 自报 reviewer）。P0 阶段允许 reviewer 为空，但必须标注 `TBD-clinician`。
