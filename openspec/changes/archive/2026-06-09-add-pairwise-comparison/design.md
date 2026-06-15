## Context

平台跨 run 对比现仅 `server/compare.py::compare_runs`：读两 run 的
`CaseResultRow.release_passed` 算 `regressions/improvements/pass_rate_delta`，
并对比 `judge_fingerprints`。这是布尔级 diff，分辨不出「都过但谁更好」。

判分内核 LLM 层有 `LLMJudge`（rubric 绝对分）与 `ScoringPointJudge`（逐点 met），
两者都是单 trace 绝对打分；裁判调用统一走 `judges/llm_backend.py::LLMBackend`
（client 构建 + 限速退避 + JSON 解析），对话渲染走 `judges/llm.py::_format_conversation`。

平台 run 落库于 `EvalRun`（含 `benchmark_id` / `total` / `config_snapshot` /
`judge_fingerprints` / `has_traces`）+ `CaseResultRow`（含 `sample_id` /
`release_passed` / trace 文本）。trace 全文也落 `outputs/<slug>/traces.jsonl.gz`。

本变更新增「用户主动发起的逐题 PK」，由用户先在前几轮对齐：**只卡判分尺子、放开被测
bot**。

## Goals / Non-Goals

**Goals:**
- 内核提供纯函数式 `PairwiseComparator`：双 trace → `A/B/tie` + 维度归属 + 理由，
  带位置消偏与医疗保守约束，零副作用、可单测（mock backend）。
- 平台提供可比性校验 + 异步发起 + 落库 + 查询；产出整体总结（胜率/维度/回退清单）
  与逐用例列表。
- 前端「Pairwise 对比」入口 + 列表 + 左右并排详情 + 总结。

**Non-Goals:**
- 三路及以上对比、线上 A/B、结论回流改阈值、导出 Excel/飞书（后续）。
- 不动 `BaseJudge` / `TestCase` / `FailureTag`，不写任何 gate。

## Decisions

### D1：`PairwiseComparator` 独立于 `BaseJudge`
`BaseJudge.judge(case, trace)` 是单 trace 契约；pairwise 天然是双 trace，强行塞进
`BaseJudge` 会污染核心节点签名。故新建 `medeval/pairwise.py`，自带 `compare_case`/
`compare_pair` 方法，**只读复用** `_format_conversation` + `LLMBackend`。
*备选*：扩 `BaseJudge` 支持双 trace —— 否决，破坏核心契约、触发循环依赖风险。

### D2：位置消偏 = 两次交换 + 取一致
对每对调两次：顺序①(A,B)、顺序②(B,A)。映射回 A/B 后：
- 两次都判 A 胜 → `winner=A, confidence=high`
- 两次都判 B 胜 → `winner=B, confidence=high`
- 不一致（含一次 tie）→ `winner=tie, confidence=low`
维度归属同法逐维度判定。`confidence=low` 占比作为「这次改动没拉开差距」的观测信号。
*备选*：单次判定 —— 否决，位置偏好会制造假胜负。

### D3：医疗保守覆盖
聚合时，若**任一顺序**里 `safety` 维度判某方更差，则整体 winner 不得为该方（降级
为 tie）。与 `llm.py` 安全敏感维度取 min、`semantic_adjudicator` 不碰 hard_gate 的
基调一致。

### D4：可比性校验——只卡判分尺子
发起前校验（任一不满足即 422 拒绝并给中文原因）：
1. `benchmark_id` 相同；
2. 两 run 的 `sample_id` 集合完全一致（不仅 `total` 数量）；
3. 判分尺子一致：`judge_fingerprints` 相等 **且** `config_snapshot.scoring` 相等。

被测差异（`config_snapshot.adapter.system_prompt` / 被测 model）**不校验**，而是 diff
出来塞进结果总结的 `subject_diff` 字段，前端显式展示。
*备选*：全 config 一致才放行 —— 否决，会废掉「换 prompt/换模型前后对比」主用例。

### D5：数据建模与落库
新增两表（轻量幂等迁移，风格对齐现有 `server/db.py`）：
- `PairwiseComparison`：id / run_a_id / run_b_id / judge_model / judge_fingerprint /
  status(running|done|failed) / created_by / created_at / 汇总 JSON（win/lose/tie、
  低置信数、各维度胜率、subject_diff、judge_logic_changed=False 恒成立因已校验）。
- `PairwiseCaseVerdict`：id / comparison_id / sample_id / winner / confidence /
  dimension_winners(JSON) / reason / swap_consistent。
trace 全文展示走已存的 `CaseResultRow` 文本，不在新表冗余存。

### D6：异步执行复用现有 Job 模式
发起即建 `PairwiseComparison(status=running)`，后台任务逐题调 comparator 并写
`PairwiseCaseVerdict`，收尾算汇总置 `done`。沿用 `server/jobs.py` 的后台执行与
启动回收孤儿模式（running 超时回收为 failed）。

### D7：成本与范围
默认对**两 run 共有的全部 sample_id** 跑（每题 2 次 LLM 调用）。提供 `scope` 入参：
`all`（默认）/ `divergent_only`（仅布尔 diff 有差异的题，省钱用于快筛）。

## Risks / Trade-offs

- [裁判模型本身不稳定/有偏] → 位置消偏 + `confidence` 透出；安全维度保守；prompt 进
  fingerprint 便于复盘。
- [成本随用例数×2 线性增长] → `scope=divergent_only` + 复用 `LLMBackend` 限速退避 +
  落库后可复看不重算。
- [两 run 判分尺子不同导致误比] → D4 硬校验直接拒绝。
- [trace 缺失（旧 run 未落 trace）] → 校验阶段检查双方 `has_traces`，缺失则拒绝。
- [并发/孤儿任务] → 复用 jobs 回收机制；`PairwiseComparison.status` 单一信任源。

## Migration Plan

- `server/db.py` 启动时幂等建新表（`CREATE TABLE IF NOT EXISTS` 同款轻量迁移），
  无破坏性 schema 变更，老数据不受影响；回滚=删两张新表与新路由，主链路零影响。

## Open Questions

- `divergent_only` 是否进 MVP？倾向 MVP 仅 `all`，`scope` 字段先预留默认 `all`。
- 前端入口位置：看板顶部全局按钮 vs run 详情页「与某 run PK」——倾向二者皆可，MVP
  先做全局入口（选两个 run）。
