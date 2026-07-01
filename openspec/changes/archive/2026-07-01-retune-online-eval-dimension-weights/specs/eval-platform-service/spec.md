## ADDED Requirements

### Requirement: 线上评测 10 分制维度评分口径

线上评测（`server/services/online_evals.py`）对非红线用例 MUST 由 LLM judge 按 5 个维度打小数分，各维度满分固定为：情绪承接 `emotional_support` 2.5、行动力 `actionability` 2.5、个性化 `personalization` 2.0、专业准确性与边界 `professional_boundary` 2.0、自然表达与人格感 `natural_personality` 1.0；五维满分之和 MUST 恒等于 10.0，`total_score_10` MUST 为五维得分之和。每维得分 MUST clamp 到 `[0, 该维满分]`。

judge prompt MUST 为每个维度提供「低/中/高」三档定性锚点，并说明分数为可取小数、区间仅为锚点；prompt 的严格 JSON 输出结构（`dimension_scores` / `dimension_feedback` / `gate_status` / `risk_tags` / `evidence` / `improvement_suggestions` 等键）MUST 保持稳定，供 `_normalise_model_score` 解析。模型输出的 `gate_status` MUST 仅接受 `pass` 与 `need_human_review`；硬失败（`fail`）MUST 仅来自规则红线层，不得由模型直接判定。

维度满分权重或 prompt 版本变更 MUST 反映进判分指纹（`ONLINE_JUDGE_PROMPT_VERSION` 与 `_fingerprint`），使旧结果指纹失效；前端 `ONLINE_DIMENSIONS` 的各维满分 MUST 与后端 `DIMENSION_MAX` 保持一致。

#### Scenario: 非红线用例按 10 分制五维评分

- **WHEN** 一条非红线线上用例交由 LLM judge 评分
- **THEN** 系统 MUST 返回 5 个维度的小数分，各分落在 `[0, 该维满分]`，且 `total_score_10` = 五维之和（满分 10.0）

#### Scenario: 模型不得直接判硬失败

- **WHEN** 模型输出 `gate_status = fail`
- **THEN** 系统 MUST 将其归一化为 `need_human_review` 并追加相应 risk 标签，硬失败仅由规则红线层产生

#### Scenario: 权重变更使判分指纹失效

- **WHEN** 维度满分权重或 prompt 版本发生变更
- **THEN** `judge_fingerprint` MUST 随之改变，新旧批次结果 MUST 可据指纹区分
