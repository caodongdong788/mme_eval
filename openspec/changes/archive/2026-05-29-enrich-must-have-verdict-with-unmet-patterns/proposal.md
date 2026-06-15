## Why

当前 Rule Judge 在 `must_have` 失败时只返回一句中文 reason —— OR 模式全 miss 时是 `"全部 must_have 均未命中"`，AND 模式时是 `"缺失：xxx, yyy"` 的字符串拼接。读飞书 docx 报告的人无法从这一行看出 case 期望命中什么模式（关键词还是正则、具体内容是什么），必须再去翻 case yaml 才能判断这是 bot 真的漏了关键信息，还是规则本身设得太严。这条信息缺失发生在每一条 must_have 失败的 case 上，是飞书报告里**最高频的可读性盲点**。

## What Changes

- `JudgeVerdict` 新增 `unmet_patterns: list[Pattern]` 字段，承载"未被命中的期望模式"清单。默认 `[]`，向后兼容旧 `report.json`。
- `RuleJudge._check_must_have` 在三种情况下填充 `unmet_patterns`：
  - OR 模式（默认）失败 → `unmet_patterns = case.expected_behavior.must_have`（全部）
  - AND 模式（`must_have_all=true`）失败 → `unmet_patterns = missing` 子集
  - 通过 → `unmet_patterns = []`（不冗余存储）
- Markdown reporter 在失败样本段渲染 `unmet_patterns` 为子列表，区分关键词与正则两种类型，反引号包裹内容避免 Markdown 转义。
- Rule judge fingerprint 不变（仅扩展输出，不改变判定逻辑），保留历史报告 diff 兼容。

## Capabilities

### New Capabilities
（无）

### Modified Capabilities
- `judging-pipeline`：`JudgeVerdict` 数据契约扩展新增 `unmet_patterns`；Rule Judge 必须在 must_have 失败时填充，通过时留空。
- `reporting`：失败样本段必须为带 `unmet_patterns` 的 verdict 渲染子列表，区分关键词与正则两类显示。

## Impact

代码：
- `medeval/models.py` — `JudgeVerdict` 加 `unmet_patterns` 字段
- `medeval/judges/rule.py` — `_check_must_have` 填充新字段（OR + AND 两条路径）
- `medeval/reporter/markdown_report.py` — `_failure_section` 渲染子列表
- `tests/test_rule_unmet_patterns.py`（新）— 单测 OR 全 miss / AND 部分 miss / 通过 三种情形
- `tests/test_markdown_report.py`（新或扩展）— 断言子列表渲染、关键词/正则区分、空 `unmet_patterns` 不渲染额外行

数据契约：
- `report.json` 新增 `verdicts[*].unmet_patterns` 字段（旧报告 load 时默认 `[]`）。下游（飞书 docx、未来 dashboard、失败聚类）可消费。

不影响：
- `transcripts.xlsx`（不展示 verdict 详情）
- `must_not_have` 渲染（命中已自带 evidence）
- Rule judge fingerprint（仅扩展输出，判定逻辑不变）
- 阈值与通过率统计（仅可读性增强）
