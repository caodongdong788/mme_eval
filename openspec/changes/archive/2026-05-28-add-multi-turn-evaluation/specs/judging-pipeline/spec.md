## ADDED Requirements

### Requirement: LLMJudge 必须以完整对话历史为判分输入

`LLMJudge` 在构造 prompt 时 MUST 把 `ConversationTrace.messages` 中**所有 user / assistant / system 轮次按时间顺序**渲染进去，而不是只取最后一轮 user 输入。这是 HardGate 既有"全量回复拼接"约束的多轮配套：HardGate 关心 bot 在哪一轮说了红旗建议；LLMJudge 关心 bot 在轮次之间是否一致、是否记得前文、是否随新信息更新建议。两者都 MUST 看完整对话才能做出可解释的判断。

渲染格式 MUST 采用显式的轮次标签 `[turn N · 用户]` / `[turn N · bot]`，其中 N 从 1 起递增，每出现一条 `role=user` 即递增（同轮的 assistant 回复共享同一个 N）。预设的 `role=system` turn MUST 以 `[系统提示]` 单独标注、不参与 N 计数。该格式 MUST 被 `LLMJudge.fingerprint()` 覆盖（即 `_PROMPT_TEMPLATE` 字面量变化 MUST 改变 fingerprint）。

#### 场景: 多轮用例的对话整段进入 prompt

- **WHEN** 一条用例有 `[user, user, user]` 三轮对话且 bot 各自回复
- **THEN** LLMJudge 发往外部 LLM 的 prompt 必须依次包含 `[turn 1 · 用户]` / `[turn 1 · bot]` / `[turn 2 · 用户]` / `[turn 2 · bot]` / `[turn 3 · 用户]` / `[turn 3 · bot]` 共 6 段；prompt 中必须不存在"最后一轮 user"这种割裂表达

#### 场景: 单轮用例向后兼容

- **WHEN** 一条用例只有一轮 user 输入和一轮 bot 回复
- **THEN** LLMJudge 必须仍能正常打分；prompt 中只渲染 `[turn 1 · 用户]` / `[turn 1 · bot]` 两段；rubric / 输出格式不变

#### 场景: 预设 system turn 必须显式标注但不计入 turn 编号

- **WHEN** 用例 turns 是 `[system: "你是儿科医生", user: ..., user: ...]`
- **THEN** prompt 必须先渲染 `[系统提示] 你是儿科医生`，然后是 `[turn 1 · 用户]` / `[turn 1 · bot]` / `[turn 2 · 用户]` / `[turn 2 · bot]`；turn 编号必须从 user 出现处开始

#### 场景: prompt 模板变化必须改变 fingerprint

- **WHEN** 开发者修改 `_PROMPT_TEMPLATE` 中任一字面量（包括 turn 标签格式）
- **THEN** `LLMJudge().fingerprint()` 返回值必须变化，`tests/test_judge_fingerprint.py::test_llm_fingerprint_stable` 必须失败强制人工 review，开发者必须在同 PR 内更新 `EXPECTED_FINGERPRINTS["llm_default"]` 硬编码值
