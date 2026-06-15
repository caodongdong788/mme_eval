# Design: Pairwise 人工校准与有效值汇总

## 数据模型（PairwiseCaseVerdict 增量列）

机器原判（对比 job 写入，校准不覆盖）：
- `winner`, `confidence`, `swap_consistent`, `dimension_winners`, `reason`, `order_runs`

人工覆写（仅 PATCH 写入）：
- `human_calibrated: bool`（默认 false）
- `human_winner: str`（A|B|tie）
- `human_dimension_winners: dict`
- `human_reason: str`
- `human_calibrated_by`, `human_calibrated_at`

## 有效值（单一信任源函数 `verdict_effective_row`）

```python
if human_calibrated:
    winner, dimensions, reason = human_*
    confidence_kind = "human"
else:
    winner, dimensions, reason = machine fields
    confidence_kind = high | order | safety  # 由 confidence+swap_consistent 派生
```

## 汇总重算

`recompute_pairwise_summary(session, comparison_id)`：
1. 加载全部 verdicts
2. `rows = [verdict_effective_row(v) for v in verdicts]`
3. `_summarize(rows)` → 写回 `comp.summary`

`_summarize` 扩展：
- `low_confidence` = 仅 `confidence_kind in (order, safety)` 计数
- 新增 `human_calibrated_count`
- `order_sensitive_count` / `safety_doubt_count` 细分（非人工）

## API 契约（PairwiseCaseVerdictOut）

对外只暴露**有效值** + 审计字段：
- `winner`, `dimension_winners`, `reason`（有效）
- `confidence_kind`: high | order | safety | human
- `human_calibrated: bool`
- 若 `human_calibrated`：`auto_winner`, `auto_confidence`, `auto_dimension_winners`, `auto_reason`

`DELETE` 校准 = 清 `human_calibrated` 并重算 summary。
