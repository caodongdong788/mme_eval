# Proposal: scoring-point-deduct-only

## Why

指南得分点应从严：**只减不加**。总扣分 = 正分未命中 + 负分踩雷，按固定 k=0.1 映射功能分；合并原「净分映射」与「负向加重」为一条线，避免重复扣。

## What Changes

- `score_case`：`function -= (miss_pos + hit_neg) * 0.1`，允许功能分为负。
- 对抗题治愈类负分点命中仍触发合规归零 + `force_fail`（不再额外 -0.35 功能）。
- 文档与 OpenSpec 更新；`scoring_point_function_cap` 不再用于功能映射（config 保留兼容）。
