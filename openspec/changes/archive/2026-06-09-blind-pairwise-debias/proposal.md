# Proposal: Pairwise 双盲匿名化消偏 + 顺序敏感分歧留痕

## Why

实跑发现大量「持平 · 低置信 · 顺序敏感」用例：换序后裁判判定翻转，最终降级持平，但展示的
理由却单方面倾向某一方，造成「理由偏 A 却判持平」的割裂感。根因有二：

1. **身份标签泄露削弱消偏**：现状 prompt 与对话块标题始终明示「系统 A=基线 / 系统 B=本次」，
   裁判每次都知道谁是基线、谁是新版，带着身份先验判定。位置消偏只交换了段落顺序、标签不变，
   盲化效果被身份泄露抵消，位置/身份偏见仍在 → 顺序敏感高发。
2. **理由展示片面**：降级 tie 后 `reason` 只取两次中某一次（判出胜负那次）的单方面说辞，
   完全不体现「另一次判了相反结论」，读起来像「明明某方更好」。

## What Changes

- **双盲匿名化消偏（机制层）**：prompt 改用中性占位「系统①（上）/系统②（下）」，**不暴露
  基线/本次身份**；裁判输出 `winner`/`dimensions ∈ {1, 2, tie}`（指代位置），`reason` 用
  「系统①/系统②」指代。两次调用交换「位置↔真实系统」映射（pass1 上=A 下=B；pass2 上=B
  下=A），代码侧把位置标签 1/2 翻译回 A/B 语义、reason 文本同步翻译。这才是真正的位置+身份
  双盲，实质降低顺序敏感。
- **Prompt 证据优先引导（prompt 层）**：增加「先逐维度列出可观察证据点，再综合判定」的结构化
  引导，使判定锚定文本证据而非位置/身份。保留既有 tie 定义、优先级与医疗保守基调（不弱化
  「别偷懒判 tie」，因其对顺序敏感不对症且有回归风险）。
- **顺序敏感分歧留痕（展示层）**：`PairwiseCaseVerdict` 新增 `order_runs`（两次 pass 的
  `{top, winner, reason}`），前端在顺序敏感用例上**如实呈现两次分歧**（顺序①→? / 顺序②→?），
  不再只摊开片面理由。

## Impact

- Affected specs: `judging-pipeline`（MODIFIED「位置消偏」；ADDED「顺序敏感分歧留痕」）
- Affected code:
  - `medeval/pairwise.py`（prompt、`_conversation_blocks`、新增 `_resolve_side`/`_relabel`、
    `compare_case` 双盲映射、`PairwiseResult.order_runs`）
  - `server/models_db.py`（PairwiseCaseVerdict 加 `order_runs` JSON 列，增量迁移）
  - `server/schemas.py`（PairwiseCaseVerdictOut 加 `order_runs`）
  - `server/pairwise_job.py`（落库 `order_runs`）
  - `frontend/src/api.ts`、`frontend/src/pages/PairwiseDetailPage.tsx`
- **fingerprint 变化（预期）**：prompt 模板改变 → `PairwiseComparator.fingerprint()` 改变，
  历史对比 diff 会标记为「判分逻辑变化」。这是有意的（消偏机制升级）。
- 不改 `winner/confidence/swap_consistent` 的对外语义（仍是 A/B/tie 与高/低），不进任何 gate，
  不影响主评测链路。
