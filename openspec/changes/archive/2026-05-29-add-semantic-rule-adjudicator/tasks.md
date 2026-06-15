## 1. 模型与配置

- [x] 1.1 在 `medeval/models.py` 的 `JudgeVerdict` 增加向后兼容字段：`adjudicated: bool = False`、`adjudication_reason: str = ""`（默认值保证历史 report.json 可加载）
- [x] 1.2 在 `CaseResult` 增加 `needs_human_review: bool = False`（默认 False，向后兼容）
- [x] 1.3 在 `config.yaml` 的 `judges.rule` 下新增 `semantic_adjudicator` 段：`enabled`(默认 false)、`provider`、`model`、`api_key_env`/`api_key`、`base_url`、`negation_prefilter.enabled`、`negation_prefilter.cues`、`cache.enabled`

## 2. 否定线索快筛（确定性，零成本）

- [x] 2.1 实现否定/条件线索邻近排除函数：输入命中片段在归一化文本中的位置 + 线索词表，输出"是否疑似误报"信号
- [x] 2.2 快筛默认作为"强信号"传给 LLM（不单独直接救回），开关可配
- [x] 2.3 为快筛补单测：`是否需要马上手术` 命中"是否需要"→强信号；纯`马上手术建议尽快`→无信号

## 3. SemanticRuleAdjudicator 核心

- [x] 3.1 新建 `medeval/judges/semantic_adjudicator.py`，定义 `SemanticRuleAdjudicator` 类（独立角色，非扩展 LLMJudge）
- [x] 3.2 复用/抽取 LLM client 构建与指数退避重试（必要时抽到 `judges/base.py` 共享）
- [x] 3.3 设计裁决 prompt：输入 bot 回复 + 命中 span + 规则方向(must_have/must_not_have) + `Pattern.note` 意图 + 快筛信号；输出严格 JSON（must_not_have 返回 `{violated, reason}`，must_have 返回 `{satisfied, reason}`）
- [x] 3.4 实现 `note` 缺失时的弱模式回退（仅正则+命中片段）
- [x] 3.5 实现裁决缓存：key=`(归一化回复, pattern 序列化, direction)`，进程内缓存保证重跑一致

## 4. 接入判分失败路径（非对称 + 安全闸）

- [x] 4.1 在 `cli.py` 判分循环中（majority 之前逐 run），仅对 `rule.*` 且 `passed=false` 的 verdict 触发裁决
- [x] 4.2 实现安全分级闸：`hard_gates.red_flag_triage != none` → 跳过救回，置 `needs_human_review=true`（裁决器天然不触碰 `hard_gate.*`）
- [x] 4.3 裁决救回 → 将 verdict 翻为 PASS，置 `adjudicated=true`、写理由、保留原 evidence；同时清除该 verdict 贡献的失败标签
- [x] 4.4 经 `recompute_result_summary` 重算 `overall_passed`，确保裁决器关闭时该路径行为与现状完全一致
- [x] 4.5 双向覆盖：must_not_have 误杀救回 + must_have 漏判救回各走独立判定

## 5. Fingerprint 与治理

- [x] 5.1 将裁决器的 prompt 模板 + provider + model + enabled + 快筛配置纳入其 fingerprint；排除 api_key/base_url 等调用配置（救回时经 `semantic_adjudicator.summary` verdict 进入 report.judge_fingerprints）
- [x] 5.2 确认 `tests/golden`（仅覆盖 hard_gate）不受影响；hard_gate/rule/llm fingerprint 未漂移，无需登记 changelog
- [x] 5.3 运行 `medeval verify-heuristics` 确认治理三检通过

## 6. 报告呈现

- [x] 6.1 在 markdown 报告中标注"被语义救回"的用例（含理由与原命中证据）
- [x] 6.2 在报告中单独切片 `needs_human_review` 用例，便于人工抽查

## 7. 测试与回归

- [x] 7.1 单测：误杀救回（bc_screen_birads3 场景）、漏判救回、不制造新失败、不触碰 hard_gate
- [x] 7.2 单测：红旗规则失败不被救且标 `needs_human_review`
- [x] 7.3 单测：相同输入重跑裁决一致（缓存）；改 prompt/model 改变 fingerprint，改 api_key 不变
- [x] 7.4 单测：裁决器关闭时判分结果与未引入前一致（向后兼容）
- [x] 7.5 为 `bc_screen_birads3` 用例补 `Pattern.note` 意图锚点；逐步为存量 must_have/must_not_have 补 note（持续）
- [ ] 7.6 开启裁决器对乳腺癌套件回归，核对已知误判被救回、无红旗用例被误救 —— 留给用户触发（会真实调用 GPT-5.1）
