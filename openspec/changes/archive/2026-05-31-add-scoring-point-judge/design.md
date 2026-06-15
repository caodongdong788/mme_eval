## Context

判分流水线现有三层：HardGate（硬门槛，一票否决）、Rule（must_have/must_not_have 正则）、LLM judge（6 个固定维度 inquiry/empathy/factual_accuracy... 各给一个 0~max 整体软分）。`RubricItem` 已带 `points: list[str]` 字段，但当前仅作为**提示文本**拼进 LLM prompt（`；评分点：...`），并未做逐点命中判定——所以"逐点打分"是缺失能力。

对标 HealthBench：每条 case 由临床专家预写一组带分值的得分点（criterion），grader 模型逐点判命中，得分 = 命中点分值之和。这是功能有效性最可解释的度量。本设计在不破坏现有任何判官的前提下，新增一个独立的 `ScoringPointJudge`，与 LLM judge 并列。

## Goals / Non-Goals

**Goals:**
- 为 `TestCase` 提供 HealthBench 式 per-case 得分点结构，支持正/负分与可选指南锚点。
- 新增 `ScoringPointJudge` 做逐点命中判定，产出软分（不改变现有 pass/fail 语义）。
- 顺带派生"指南匹配率"指标，避免本期就建外部指南要点库。
- 保持复现性：fingerprint、N-runs 单次调用、缓存友好、向后兼容历史报告。

**Non-Goals:**
- 不设指南匹配率否决阈值（本期只展示，合格判定后续 change 再定）。
- 不替换 Rule / must_not_have（正则做便宜的确定性硬检查，得分点做语义细判，二者共存）。
- 不做加权综合分与评级（属 `add-weighted-scoring-and-grading`）。
- 不建集中式指南要点库（锚点先长在 case 的得分点上，集中化是后续优化）。

## Decisions

### 决策 1：得分点结构与负分语义
新增 `ScoringPoint` model：`criterion: str`、`points: int`（可负）、`guideline: str = ""`、`critical: bool = False`。`TestCase.scoring_points: list[ScoringPoint] = []`。
- 正分点：命中即得 `points`，表达"该说的"。
- 负分点：命中即扣 `|points|`（即净加 `points`，points 为负），表达"出现即惩罚"，与 must_not_have 互补但走语义判定。
- 归一化：`achieved = Σ(命中点的 points)`；`max_positive = Σ(points>0 的 points)`；`normalized = clip(achieved / max_positive, 0.0, 1.0)`。`max_positive == 0`（全是负分点）时定义 normalized = 1.0 当无命中、0.0 当有负分命中（边界在 spec 中固化）。
- **备选**：复用现有 `RubricItem.points`。否决——那是固定 6 维下的提示串，无分值/锚点/正负语义，承载不了 per-case 任意得分点。

### 决策 2：独立判官而非扩 LLM judge
新建 `ScoringPointJudge`（`judges/scoring_point.py`），与 `LLMJudge` 平级，复用其 LLM client 构建与重试逻辑。
- 理由：LLM judge 是"固定维度整体打分"，得分点是"任意条目逐点判定"，prompt 与输出 schema 不同；混在一起会让两者的 fingerprint 互相污染。
- verdict 命名 `scoring_point.*`，`score`/`max_score` 填归一化前的净得分与正分总额，`reason` 给逐点命中摘要，`evidence` 给命中片段。

### 决策 3：软分、不阻塞 overall_passed
`scoring_point.*` verdict 归入软分（类比 `llm.*`），**不参与** `overall_passed` 与 `hard_gate_passed`。
- 理由：本期定位是"度量功能有效性"，否决仍由 HardGate 负责；这样历史用例（无得分点）行为零变化，也不需要新增阻塞性失败标签。

### 决策 4：指南匹配率为派生指标
在带 `guideline != ""` 的得分点子集上：`指南匹配率 = 命中数 / 该子集总数`（按点计数，不按分值加权，避免负分点扭曲）。
- 写入 `CaseResult`（派生字段）与 `RunReport` 聚合，报告展示；**不设阈值、不否决**。
- 理由：解锁用户"指南要点库后面再定"的诉求——锚点先随 case 走，集中库是后续优化。

### 决策 5：N-runs 单次调用 + fingerprint
- 沿用既有约定：确定性判官（HardGate/Rule）对每个 trace 跑；`ScoringPointJudge` 是 LLM 判官，**只对代表性 trace 调一次**（控成本，与 LLM judge 一致）。
- `fingerprint()` 覆盖 prompt 模板 + provider + model + temperature；**不**覆盖 case 的得分点内容（那是用例数据，变动由 `case_version` 追踪）。救回/打分经 `scoring_point.summary` verdict 把 fingerprint 带入 `report.judge_fingerprints`。

### 决策 6：配置与开关
`config.yaml` 新增 `judges.scoring_point`：`enabled`（默认 true，但无得分点的 case 自动跳过、零 API 调用）、`provider`/`model`/`api_key_env`/`base_url`/`api_version`/`temperature`。复用 LLM 基建配置形态。

## Risks / Trade-offs

- [LLM grader 逐点判定不稳定，可能抖动] → temperature=0.0 + N-runs 只对代表性 trace 调用 + 严格 JSON 输出（每点 `{met: bool, reason}`）；后续可加缓存。
- [负分归一化在"全负分点"边界语义模糊] → 在 spec 用明确 Scenario 固化边界，避免实现各自发挥。
- [得分点写作成本高（需临床专家）] → 本期只为少量样例 case 补点示范；存量 case 渐进补充，judge 对空得分点零成本跳过。
- [新判官污染 fingerprint 治理] → 独立 fingerprint，不动 HardGate 黄金集；`verify-heuristics` 三检不受影响。
- [指南匹配率被误读为"合格线"] → 报告文案明确标注"仅度量、未设否决"，与 HardGate 通过率分开呈现。

## Open Questions

- 指南匹配率最终是否进入合格判定、阈值多少 → 留给后续 change（用户已明确本期只打分）。
- 是否需要把得分点命中也纳入失败标签体系（如 `guideline_mismatch`）→ 暂不引入，保持软分非阻塞；若后续设否决再议。
