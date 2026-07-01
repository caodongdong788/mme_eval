# Proposal: 线上评测维度重配（满分 9→10）与 judge prompt 优化

## Why

线上评测（`server/services/online_evals.py`）用一条 LLM judge prompt 给 5 个维度打小数分，五维满分之和当前 = 9.0，但对外一直号称「10 分制」（`total_score_10`、路由注释、prompt 首句），存在口径不一致。同时现有 prompt 每维只有一句话描述、无逐档锚点，小数分校准全靠模型自由裁量、可复现性弱。

## What

- 重配维度满分，使五维之和 = 10.0：情绪承接 `emotional_support` 2.0→2.5、专业准确性与边界 `professional_boundary` 1.5→2.0，其余不变（行动力 2.5 / 个性化 2.0 / 自然表达与人格感 1.0）。
- 优化 judge prompt：新增「证据先行」评分方法，五维补「低/中/高」三档不重合区间锚点，并明确「区间只是锚点，可在区间内或相邻档之间灵活取任意小数」；`请输出严格 JSON` 输出契约保持不变。
- `ONLINE_JUDGE_PROMPT_VERSION` v1→v2；`_fingerprint` 已含 `DIMENSION_MAX`，权重与 prompt 变更 MUST 使旧结果指纹失效。
- 评级阈值 `_grade`（≥9/≥8/≥7/≥6）在 10 分制下刻意保持不变。
- 前端 `ONLINE_DIMENSIONS` 满分与后端对齐；新增回归断言锁死五维和 = 10。

## Impact

- `server/services/online_evals.py`（`DIMENSION_MAX`、`_online_judge_prompt`、`ONLINE_JUDGE_PROMPT_VERSION`）
- `frontend/src/hooks/useOnlineEvalsPage.ts`（`ONLINE_DIMENSIONS`）
- `tests/server/test_online_evals.py`（新增满分口径断言）
- OpenSpec: `eval-platform-service`
- 口径变更：新旧批次的 `total_score_10` 与维度分不可跨版本直接比较，`judge_fingerprint`（v2）已能区分；历史批次分数不回改
