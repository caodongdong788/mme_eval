## Why

现有判分对"临床内容到底对不对"只有两种手段：Rule 的字面正则（脆、表达一变就漏）和 LLM judge 的 6 个固定维度整体软分（粒度粗、无法说清"哪条该说的没说"）。对标 HealthBench，缺的是**由临床专家为每条用例预先写好的"得分点"，再让模型逐点判定命中/未命中**——这是衡量功能有效性（知识准确性、内容完整性）最可解释、最贴临床的方式。同时，只要给得分点挂上指南锚点，就能顺带派生出"指南匹配率"，无需先建外部指南要点库。

## What Changes

- 在 `TestCase` 新增 `scoring_points` 字段：每条 case 可声明一组专家得分点，每个点含 `criterion`（要点描述）、`points`（整数，**可为负**，命中负分点即扣分，用于惩罚不该出现的内容）、`guideline`（可选指南锚点）、`critical`（是否关键点）。默认空列表，向后兼容。
- 新增 `ScoringPointJudge`（`medeval/judges/scoring_point.py`）：对声明了得分点的 case，用 LLM grader **逐点判定**命中与否，输出 `scoring_point.*` verdict（软分、**不阻塞** `overall_passed`）。归一化得分 = 命中点净得分 / 正分总额，clip 到 0~1。
- 派生**指南匹配率**：在带 `guideline` 锚点的得分点子集上统计命中占比。**本期只计算并展示，不设否决阈值**（是否纳入合格判定后续再定）。
- 复用现有 LLM 基建并遵守既有复现红线：本判官有独立 `fingerprint`、在 N-runs 下只对代表性 trace 调用一次。
- 报告新增"得分点逐点命中 + 指南匹配率"展示段。
- `config.yaml` 新增 `judges.scoring_point` 配置段。

## Capabilities

### New Capabilities
<!-- 无新增 capability，得分点判官归属既有 judging-pipeline -->

### Modified Capabilities
- `case-schema-and-loader`: `TestCase` 新增 `scoring_points` 字段及其校验，loader 必须能加载/校验得分点结构。
- `judging-pipeline`: 新增 `ScoringPointJudge`（逐点打分 + 负分语义 + 指南匹配率派生 + fingerprint + N-runs 单次调用）。
- `reporting`: 报告新增得分点命中明细与指南匹配率切片。

## Impact

- 代码：`medeval/models.py`（`TestCase` + 新 `ScoringPoint` model + verdict/result 字段）、新增 `medeval/judges/scoring_point.py`、`medeval/judges/aggregator.py`、`medeval/judges/__init__.py`、`medeval/cli.py`、`medeval/reporter/markdown_report.py`、`config.yaml`、`cases/`（为样例 case 补 `scoring_points`）、`tests/`。
- 兼容性：所有新增字段带默认值，历史 `report.json` 与无 `scoring_points` 的 case 行为不变；判官关闭或 case 无得分点时不发起任何 API 调用。
- 依赖：复用既有 Azure/OpenAI LLM 客户端，无新增第三方依赖。
