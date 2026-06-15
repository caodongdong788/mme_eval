# Proposal: Pairwise 对比——同一裁判模型逐题 PK 两次评测

## Why

平台现有的跨 run 对比只有 `server/compare.py` 的**布尔 diff**（基于 `release_passed`
翻转，产出 `regressions / improvements / pass_rate_delta`）。它只能回答「这题从过变挂」，
答不出图里「Agent Eval」最常见、最有价值的问题：

- 同一道题，A、B 两版回答**即便都过（或都挂），到底哪个更好、好在哪**？
- 换了 `system_prompt` / 换了被测模型后，新版**整体质量是涨还是跌**，涨/跌集中在哪个维度？

LLM Grader 这一层目前只有**绝对打分**（`llm.py` rubric / `scoring_point.py` 逐点），缺
图里强调的 **Pairwise 对比**——而模型当裁判时，「A vs B 谁更好」通常比「这答案值几分」
更稳、更贴合频繁迭代（换 prompt/换模型）的诉求。本变更补齐这一能力，做成用户**主动
发起**的对比动作。

## What Changes

- **判分内核**：新增 `medeval/pairwise.py` —— `PairwiseComparator`，对同一 `sample_id`
  的两份 `ConversationTrace` 让同一 LLM 裁判判 `A / B / tie` + 各维度归属 + 理由。
  - **位置消偏（MUST）**：每对判两次、A/B 交换顺序；两次一致才算决定性胜负，否则记
    `tie` + `confidence=low`。
  - **医疗保守**：任一顺序里 `safety` 维度判某方更差，整体不得判该方 win（沿用「分歧
    取低分」基调）。
  - 复用 `LLMBackend`（限速/退避/JSON 解析）与 `llm._format_conversation`；产出
    `fingerprint`（prompt 模板 + provider + model + temperature + 交换消偏开关）。
- **平台后端**：
  - `POST /api/compare/pairwise`：入参两个 run id + 裁判模型（从判分模型库下拉），
    **可比性校验**通过后异步发起，逐题 PK 并落库；产出一个 `PairwiseComparison` 记录。
  - `GET /api/compare/pairwise/{id}`：返回总结（整体胜率、按维度胜率、回退用例清单）
    + 逐用例列表。
  - **可比性校验（只卡判分尺子，放开被测 bot）**：两个 run MUST `benchmark_id` 相同、
    `sample_id` 集合完全一致、判分尺子一致（`judge_fingerprints` + `scoring`
    config_snapshot 相同）；判分尺子不一致 → 拒绝并提示「尺子不同不可比」。被测参数
    （`system_prompt` / 被测 model）允许不同，差异在总结里**显式列出**而非拦截。
- **前端**：看板新增「Pairwise 对比」入口 → 选两次 run（A 基线 / B 本次）+ 裁判模型 →
  发起 → 结果页含①整体总结（胜/平/负 + 按维度胜率 + 回退清单 + 被测差异说明）②逐
  用例对比列表（可按结论筛选/排序）③点进详情：A/B 完整对话左右并排 + 该题判定理由
  + 各维度谁胜。

## Impact

- Affected specs：`judging-pipeline`（新增 pairwise 比较能力与消偏/保守约束、fingerprint）、
  `eval-platform-service`（新增 pairwise 发起/查询 API、可比性校验、落库与迁移）、
  `eval-platform-dashboard`（Pairwise 对比入口/列表/详情/总结）。
- Affected code：新增 `medeval/pairwise.py`；`server/compare.py`（可比性校验复用/扩展）、
  `server/models_db.py`（新表 `PairwiseComparison` / `PairwiseCaseVerdict` + 轻量迁移）、
  `server/schemas.py`、`server/routers/`（新 router 或扩 runs）、`server/db.py`(迁移)、
  `frontend/src/api.ts`、`frontend/src/pages/`（新页面/组件）。
- **不触碰核心节点**：`PairwiseComparator` 不继承 `BaseJudge`（签名是双 trace，与单 trace
  的 `BaseJudge.judge` 不同），仅**只读复用** `TestCase` / `ConversationTrace` /
  `LLMBackend`；不新增/不修改 `FailureTag`；不写 `release_passed` / `gate_passed` /
  `hard_gate.*`（pairwise 是相对偏好，不进任何 gate）。
- 非目标（保持不变，留待后续）：三路及以上多版本对比、线上 A/B Test 真实指标、把
  pairwise 结论自动回流改 LLM judge 阈值、pairwise 结果导出 Excel/飞书。
