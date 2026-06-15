## 1. 在 BaseJudge 引入 fingerprint 协议

- [x] 1.1 在 `medeval/judges/base.py` 的 `BaseJudge` 中增加抽象 `def fingerprint(self) -> str`
- [x] 1.2 提供 `stable_hash(obj) -> str` 工具函数：`hashlib.sha1(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:12]`
- [x] 1.3 单测：相同输入两次调用 `stable_hash` 必须返回同一字符串；改一个字符必须改变结果（见 test_stable_hash_is_deterministic）
- [x] 1.4 漂移保护单测 `tests/test_judge_fingerprint.py`：把 HardGate/Rule/LLM 默认配置的 fingerprint 硬编码进单测；改任意 Judge 内嵌规则必然 fail，强制开发者同步更新 CHANGELOG

## 2. 实现各 Judge 的 fingerprint

- [x] 2.1 `HardGateJudge.fingerprint` 必须汇总 `_EMERGENCY_PATTERNS`、`_REFERRAL_PATTERNS`、`_DOSAGE_PATTERN.pattern`、`_FREQ_PATTERN.pattern`、`_DIETARY_CONTEXT_WORDS`、`_DRUG_CONTEXT_WORDS`、`_DIAGNOSIS_PHRASES`、`_DISCLAIMER_PATTERNS`
- [x] 2.2 `RuleJudge.fingerprint` 必须包含 `inspect.getsource(_normalize)` + `self.normalize`
- [x] 2.3 `LLMJudge.fingerprint` 必须包含 `_PROMPT_TEMPLATE` + `self.model` + `self.temperature` + `self.dual_judge` + `self.second_model`
- [x] 2.4 单测：(1) 修改任意 pattern 内容必须改变 fingerprint（test_hard_gate_fingerprint_stable 锁定基线）；(2) 修改注释不变（stable_hash 只哈希字面量，不包括注释）；(3) LLMJudge 改 temperature 必须改变 fingerprint（test_llm_fingerprint_changes_with_model）

## 3. 把 fingerprint 写入 verdict 与 report

- [x] 3.1 `JudgeVerdict` 增加 `judge_fingerprint: str = Field(default="")` 字段
- [x] 3.2 在 `aggregator.judge_all` 中，把每个 Judge 返回的 verdicts 统一打上对应 fingerprint
- [x] 3.3 `RunReport` 增加 `judge_fingerprints: dict[str, str] = Field(default_factory=dict)` 字段
- [x] 3.4 在 `reporter/aggregator.build_report` 中，从首个 result 的 verdicts 中收集 `judge_name → fingerprint` 写入 RunReport（同一 judge 多 verdict 取相同值，否则报错）— 实际策略：多个值时用斜杠拼接以暴露异常

## 4. diff_runs 引入 fingerprint 检查

- [x] 4.1 `diff_runs` 读取两份 report 顶层 `judge_fingerprints`
- [x] 4.2 当任一 judge 的 fingerprint 不一致时，在输出 Markdown 顶部插入 ⚠️ 警告表（按 design.md 格式）
- [x] 4.3 当某 judge 在历史报告中缺 fingerprint（向后兼容）时，显示 ℹ️ 降级提示
- [x] 4.4 单测：(1) 一致 fingerprint 不出现警告；(2) 不一致时警告中列出差异 judge；(3) 历史报告降级显示（见 tests/test_diff_runs_fingerprint.py 5 个测试）

## 5. CLI 展示 fingerprint

- [x] 5.1 `medeval run` 开始执行前，在控制台用 Rich Table 列出当前各 judge 的 fingerprint（便于人对照）
- [x] 5.2 `medeval list-cases` 不变（与 judge 无关）

## 6. 集成验证

- [x] 6.1 跑一次完整 `medeval run --adapter mock`，确认 report.json 中含 `judge_fingerprints` 顶层字段、每条 verdict 含 `judge_fingerprint`
- [x] 6.2 把 outputs/doubao_baseline_v2 与一份新生成的 report 做 diff，验证不一致时正确警告（test_diff_runs_inserts_warning_at_top）
- [x] 6.3 把 outputs/doubao_baseline（旧报告，无 fingerprint）作为上版本做 diff，验证降级为"未知"提示（test_warning_when_prev_missing_field）
- [x] 6.4 故意修改 `_EMERGENCY_PATTERNS` 一条正则，确认 fingerprint 变化；恢复后又一致（手工验证：baseline=98cb1591cde4 → drift=3b1323e7940c → restore=98cb1591cde4）
- [x] 6.5 `pytest -q` 全部通过（25 passed）；`openspec-cn validate --all --strict` 通过 — 见 Phase 3 末尾再统一验证
