## Context

医疗 chatbot 评测框架（medeval）已具备多轮对话执行能力（dialog-runner spec 已落地），但用例库 100% 单轮、LLM Judge prompt 也只看最后一轮 user 输入。在与用户的 explore 阶段确认了以下方向：

- 用例量级：40 条，按对话深度切 4 个 bucket（2/3/4/5 轮各 10 条）
- 用例组织：新顶层目录 `cases/multi_turn/`，深度作为新主轴
- 配套改造：必须同步更新 LLM Judge prompt，否则 `multi_turn_consistency` 维度无法真实打分（评估证据不全）
- fingerprint 影响：LLM Judge fingerprint 必然变化，但不需要 `heuristics-changelog.md` 登记（该 CHANGELOG 仅治理 HardGate）

利益相关方：评测框架维护者（确保单一 run 仍能稳定跑完）、临床评审者（用例必须医学合理）、模型迭代方（依赖 multi-turn 信号做模型选型）。

## Goals / Non-Goals

**Goals:**

- 把"对话深度"打造成一个可量化、可单独切片、可回归的评测压力轴
- 让 `multi_turn_consistency` rubric 维度首次具备真实判分能力（LLM Judge 能看到完整对话）
- 不破坏既有报告兼容性：现有的 by_level / by_scenario / by_population 切片继续工作
- 单 PR 内交付，前后同步：用例 + judge prompt + 测试 fingerprint 一并更新

**Non-Goals:**

- 不改 `case-schema-and-loader` spec —— 多轮能力本就在 Turn schema 中
- 不改 `dialog-runner` spec —— Runner FSM 已支持任意长度 turn 序列
- 不引入"按 turn_depth 分组"的报告聚合切片（这是后续 reporter 的 nice-to-have，本次不做）
- 不激活 `DIALOG_BREAK` 等预留失败标签的自动 emit（仍归属 `llm-judge-emit-failure-tags` 后续提案）
- 不构造 6+ 轮极长对话（成本陡增、临床收益边际下降，5 轮足以暴露主要塌方模式）

## Decisions

### 决策 1：用例目录新开 `cases/multi_turn/` 顶层而非塞进 L2_scenarios

**选择**：在 `cases/` 根下新建 `multi_turn/`，与 L1-L4 平级。

**为什么**：

- 多轮用例本身横跨 L2/L3/L4 三个 level（红旗、对抗、业务场景都要测），塞进任一 level 目录都会破坏"目录 = level"的语义
- 用例内部的 `level` 字段仍正常取值，所以 by_level 报告切片不破
- 顶层目录让"按深度跑"非常顺手：`medeval run --include cases/multi_turn/depth_5.yaml`

**取舍**：破例了"所有 case 都在 L1-L4 之下"的隐含约定，但收益（深度作为正交轴的清晰度）大于成本。

**Alternative considered**：方案 Y——按 level 散在 L2/L3/L4 各自下面，每个 level 各开 4 个 depth 文件，共 12 个新文件。被否：文件爆炸、混合归属用例无处安放。

### 决策 2：每个 depth bucket 内按"失败模式 × level"严格混搭

参见 proposal.md 提到的失败模式 × 深度配比矩阵。每个深度的 10 条 case 都包含红旗、对抗、业务场景的混合，避免"depth_5.yaml 全是对抗题"这种偏置。

**为什么**：

- 模型选型最关心的指标是"depth=N 时整体通过率"，所以同一深度内必须分布合理
- 深度间应保持失败模式同构，便于 diff 出"是 bot 在 depth=4 时记忆掉了，还是 depth=4 题更难"

### 决策 3：LLM Judge prompt 渲染采用 `[turn N · 用户/bot]` 格式

```
[turn 1 · 用户] 我胸口闷
[turn 1 · bot]  能描述一下疼痛性质吗
[turn 2 · 用户] 左肩疼+冷汗
[turn 2 · bot]  立即拨打 120
```

**为什么**：

- 中文 LLM 对自然语言标签解析更稳，对 XML/ChatML 反而容易把 `<assistant>` 当成代码片段
- 调试时人类阅读最直观
- 显式的 turn 编号让 prompt 里能写"请检查 bot 在 turn 2 给出的建议是否与 turn 1 的追问一致"

**Alternative considered**：方案乙 ChatML 风格 `<user>...</user>`，被否（中文分词问题 + 调试不友好）。

### 决策 4：单 OpenSpec change 内同时交付用例 + judge prompt 升级

**为什么**：

- 两者强耦合：用例里声明了 `multi_turn_consistency` rubric，但 prompt 看不到完整对话就打不准 → 只加用例不改 prompt 是"半成品"
- 单 PR 评审 reviewer 能一次看完整逻辑：用例的失败模式 + prompt 是否真能评估
- 不引入跨 PR 时间窗内"用例已合并、prompt 还没改"的尴尬中间状态

**Alternative considered**：拆成两个 sequential change（先 prompt 后用例 / 先用例后 prompt）。被否：增加协调成本，单 PR 已经在可控规模。

### 决策 5：`multi_turn_consistency` rubric 在 multi-turn case 里**默认开启**，单轮 case 不开

**为什么**：

- 单轮 case 谈不上"多轮一致性"，开了会让 LLM Judge 给个 0~max 的随机分污染聚合
- 多轮 case 默认 `multi_turn_consistency: { max: 2 }`，让模型迭代时能看到这个维度的曲线

### 决策 6：自伤威胁多轮用例（`l4_mt_pressure_no_referral`）走 `red_flag_triage: required_emergency`

**为什么**：

- 自伤倾向不论以何种话术、第几轮出现都是红旗，必须 hard_gate 兜底
- 即便对抗集本意是测"边界塌方"，但红旗硬门槛优先级更高
- 这条 case 既算 L4 也算 L3——但 schema 不支持 dual-level，定为 `level: L4` 但 `tags: [red_flag, adversarial, multi_turn, self_harm]` 让它在两类切片都被召回

### 决策 7：测试 fingerprint 直接更新硬编码值，不引入"宽容期"

`tests/test_judge_fingerprint.py` 中 `EXPECTED_FINGERPRINTS["llm_default"]` 必须更新为新 prompt 模板对应的新 hash。无中间过渡态。

**为什么**：

- 漂移保护测试本来就是设计给"prompt 变了必须人工确认"的强制 review 机制
- 这次变化是有意为之、proposal 里已经显式 ack，因此通过测试更新走"人工 review 已发生"的路径合规

## Risks / Trade-offs

**[Risk] LLM Judge prompt token 数变长导致触发模型上下文上限或单调用涨价**

- 5-turn 用例的对话可能 1500-3000 tokens，加 rubric 总 prompt 大约 3500-5000 tokens
- 主流模型（gpt-4o-mini、doubao-seed-pro 等）32K 上下文绰绰有余，不存在硬截断风险
- → Mitigation：在 design 里固定 prompt 模板里只渲染 `bot reply` 而非 `raw_response` 全字段，避免 raw 工具调用 trace 把 prompt 撑爆

**[Risk] 40 条新用例引入用例库不平衡**

- 当前总量 ~100 条，加 40 条相当于多轮占比从 0% 跳到 ~29%
- 模型在多轮上的失败会显著拉低整体通过率，可能让"整体 pass rate"指标看起来突然变差
- → Mitigation：报告里始终用 by_level 切片读，**不要看裸 overall pass rate 做模型选型**，proposal 的 Impact 里已显式声明这点；后续可考虑给"按 turn_depth 切片"加专门 dashboard

**[Risk] 用例内 `must_have` 关键词在多轮场景下命中率难以校准**

- 单轮用例的 `must_have` 是"bot 在唯一一次回复里提到 X"；多轮里 bot 可能在 T2 才说 X，但拼接后仍命中
- HardGate 已经按全量拼接判定，这个语义对多轮天然友好
- → Mitigation：用例编写时在 `notes` 字段写清"期望 X 出现在哪一轮"，便于人审看证据

**[Risk] 假记忆诱导用例（⑦）的判分依赖 bot 主动否认，但 must_have 难以匹配各种否认表述**

- bot 可能用"我之前并没有给您建议具体剂量""请以医生处方为准"等多种话术
- 单纯 `must_have: [keyword: "没有"]` 会误伤
- → Mitigation：这类 case 主要靠 `hard_gates.no_prescription` + LLM Judge 的 `multi_turn_consistency` 联合判定，rule judge 只做兜底；在 `failure_tags_candidates` 里同时列 `IMPROPER_PRESCRIPTION` 和（未来）`DIALOG_BREAK`

**[Trade-off] 不改 reporter 加 by_turn_depth 切片**

- 短期内"按深度切片看通过率"必须靠 `--include cases/multi_turn/depth_N.yaml` 跑多次或人工 grep 报告
- 收益与本次 change 主线（用例 + prompt）耦合度低，且 reporter 改动会再触发新的 fingerprint 治理讨论
- → 留给后续提案 `add-turn-depth-reporting`

**[Trade-off] 5 轮以上不覆盖**

- 真实生产对话有 10+ 轮的；5 轮可能低估了上下文窗口耗尽场景
- 但 5 轮已能暴露上下文记忆、漂移、施压主要失败模式；6-10 轮的边际信号不值得 2× 成本
- → 留给后续 `add-deep-context-evaluation`，且需要先有上下文长度专项工具

## Migration Plan

由于这是纯加法（新文件 + 现有文件升级），无 schema 破坏，迁移极简：

1. 合并 PR
2. 下次 `medeval run` 自动包含新用例（`cases/` 是默认 include）
3. 旧报告对比：`medeval diff_runs` 会标记 LLM Judge fingerprint 变化，正常输出
4. 用户若需要单独跑多轮：`medeval run --include cases/multi_turn/`
5. 用户若需要排除多轮（例如保持与历史报告完全可比）：`medeval run --exclude cases/multi_turn/`

回滚策略：单 PR 整体 revert 即可；无需数据迁移、无需配置迁移。

## Open Questions

无。所有关键决策已在 explore 阶段与用户对齐：

- ✓ 40 条 = 4 深度 × 10
- ✓ 顶层 `cases/multi_turn/` 目录
- ✓ 自伤威胁走 hard_gate emergency
- ✓ Prompt 渲染选 `[turn N · 用户/bot]` 方案甲
- ✓ 单 change 同时交付用例 + prompt 升级
