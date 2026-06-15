## 为什么

每个 Judge 内部都有大量"代码内嵌的规则"决定判分结果：

- `HardGateJudge` 的 `_EMERGENCY_PATTERNS` / `_DRUG_CONTEXT_WORDS` / `_DIETARY_CONTEXT_WORDS` 等近 10 张词表
- `LLMJudge` 的 `_PROMPT_TEMPLATE`（顶层 module 常量）
- `RuleJudge` 的归一化策略

这些规则任何一次修改都会改变判分结论——例如当前 `outputs/doubao_baseline_v2/report.json` 的 description 里写着"judge v2：修复假阳性处方 + 红旗 regex 放宽"，这次"判分逻辑迭代"完全靠 **run name 与一句人工 description** 来追溯，report.json 里没有任何机器可读字段能识别"这两次评测用的是不同 judge 版本"。

随之而来的具体问题：

1. **diff_runs 失效**：`diff_runs` 会把"上版本 passed 当前 failed"的用例标为 regression，但当 judge v2 把判分变严时，这些"regression"其实是判分变化而非 bot 退化——产品决策被误导。
2. **重跑历史 run 不可复现**：把 outputs/doubao_baseline（v1 judge）拿到 v2 judge 下重跑，结论可能完全不同；但没有任何元数据能告诉使用者"这是不同 judge"。
3. **关键词表演进无审计**：3 个月后回看，谁也说不清 `_DIETARY_CONTEXT_WORDS` 何时加进来，对哪些历史 case 翻转了结论。

LLM-as-Judge 一旦在 P1 默认开启，这个问题会被放大一个数量级——prompt 改一个字，分数分布就可能漂移。

## 变更内容

- **新增** 每个 Judge 必须暴露一个 `fingerprint() -> str` 方法，返回稳定哈希（sha1 前 12 位），覆盖该 Judge 所有"会影响判分的内嵌规则"。
- **新增** `JudgeVerdict` 增加 `judge_fingerprint: str` 字段，记录产生该 verdict 时的 judge 版本指纹。
- **新增** `RunReport` 顶层增加 `judge_fingerprints: dict[str, str]`（judge_name → fingerprint），便于跨 run 一眼对比。
- **修改** `diff_runs` 必须在两份 report 的 `judge_fingerprints` 不一致时显式警告，避免误把"判分变化"识别为"bot 退化"。
- **修改** `reporting` spec：JSON 报告中新增的 fingerprint 字段必须不破坏现有结构（仅追加）。

## 功能 (Capabilities)

### 新增功能

无。

### 修改功能

- `judging-pipeline`: 每个 Judge 暴露版本指纹；Verdict 携带指纹。
- `reporting`: RunReport 与 diff_runs 引入跨版本 judge 一致性校验。

## 影响

- **代码**: `medeval/judges/{base,hard_gate,rule,llm,aggregator}.py`、`medeval/models.py`（新增字段）、`medeval/reporter/diff.py`、`medeval/reporter/aggregator.py`。
- **报告兼容性**: 新字段对历史 report.json **向后兼容**——历史报告读不到新字段时按"未知 fingerprint"处理。
- **CI**: 无新依赖；fingerprint 计算开销 < 1ms 可忽略。
- **测试**: 必须新增"修改 _EMERGENCY_PATTERNS 后 fingerprint 必须改变"的回归测试。
