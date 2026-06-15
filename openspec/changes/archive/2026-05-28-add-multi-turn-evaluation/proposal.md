## Why

当前 100+ 用例**全部为单 turn**，但框架自身（Turn schema、Runner FSM、`multi_turn_consistency` rubric、`DIALOG_BREAK` 失败标签）已为多轮对话准备好。也就是说：评测框架在「对话深度」这一关键能力维度上**完全没有可观测信号**——bot 是否记得前文、是否随轮次调整建议、是否在持续施压下守住边界，目前 0 用例覆盖。

医疗咨询的真实失败模式恰恰高发于多轮：用户在第 2-3 轮才暴露红旗（"其实我嘴还有点歪"），或在 bot 给出就医建议后反复施压要剂量，或在第 4-5 轮借"按你刚才说的"诱导假记忆。本次提案补上这个评测盲区，并把"轮次深度"作为一个独立、可观测的压力轴纳入评测体系。

## What Changes

- 新建顶层目录 `cases/multi_turn/`，按对话深度切分 4 个文件，每个文件 10 条用例：
  - `depth_2.yaml` / `depth_3.yaml` / `depth_4.yaml` / `depth_5.yaml`
  - 共 40 条新用例，覆盖 9 类多轮失败模式（上下文记忆、红旗逐步浮出、人群晚暴露、边界塌方、免责漂移、主动追问、假记忆诱导、主题漂移、完整问诊闭环）
  - 用例内 `level` 字段仍取 L2/L3/L4（红旗类→L3、对抗类→L4、其余→L2），保持与现有按 level 切片报告兼容
- 修改 `medeval/judges/llm.py` 的 `_PROMPT_TEMPLATE`：从「最后一轮 user 输入 + 全量 bot 回复」改为**完整对话历史按轮次顺序渲染**（格式 `[turn N · 用户/bot]`），让 LLM Judge 真正具备评估 `multi_turn_consistency` 等多轮维度的证据基础
- 更新 `tests/test_judge_fingerprint.py` 中 `llm_default` 的硬编码 fingerprint（prompt 模板字面量变化必然触发，是漂移保护机制的预期行为）

## Capabilities

### New Capabilities

无。本次提案不新增 capability，所有改动落在既有 capability 内。

### Modified Capabilities

- `judging-pipeline`：新增一条需求约束 LLM Judge 必须基于完整对话历史（按轮次顺序）打分，而非仅最后一轮 user 输入；这是与既有"HardGate 必须以全量回复拼接为判分文本"对应的多轮配套约束。

## Impact

**受影响代码**

- `medeval/judges/llm.py` — `_PROMPT_TEMPLATE` 重写、新增 `_format_conversation` 工具函数、`judge()` 内不再单独取 `user_last`
- `tests/test_judge_fingerprint.py` — 更新 `EXPECTED_FINGERPRINTS["llm_default"]` 硬编码值
- `cases/multi_turn/depth_{2,3,4,5}.yaml` — 新增 4 个 YAML 文件共 40 条用例

**不受影响**

- HardGate / Rule Judge 行为完全不变（HardGate 已经按全量回复打分，规则 judge 只做正则匹配）
- Runner / Adapter / Reporter 行为完全不变
- `case-schema-and-loader` / `dialog-runner` spec 无变化（多轮能力本就在 schema 和 runner 中已存在）
- `docs/heuristics-changelog.md` 不变（该 CHANGELOG 仅治理 HardGate 关键词表）

**版本对比影响**

- LLM Judge fingerprint 会变化（prompt 模板变了，判分语义改变）。`diff_runs` 工具会把这次变化标记为"判分逻辑变化"，提示历史报告与新报告之间的 LLM 维度不可直接对比。这是预期行为，不是 bug。
- HardGate / Rule Judge fingerprint 不变。

**评测成本**

- 单次完整 run 的 Adapter 调用从 ~100 增至 ~240（+140）
- LLM Judge 单次 prompt token 增加（从只看最后一轮 user 变成看完整对话），多轮用例的 prompt 比单轮长 3-5 倍
- 默认 `concurrency=4` 下整体延迟增加约 2 分钟（按真实 API 估算），可接受
