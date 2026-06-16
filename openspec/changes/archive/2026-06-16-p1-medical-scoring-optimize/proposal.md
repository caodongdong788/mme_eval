# Proposal: P1 医疗打分体系全量优化

## Why

P0 已落地 scoring_point 进功能分、扣分步长 0.15、红旗 must_have_all、问诊 rubric。
审计 P1 剩余项（口径去重、权重重分配、语义裁决收紧、高危重扣、隐式红旗、人群/agent
profile、HITL 主动抽样与校准闭环）须按顺序补齐，形成可区分三类模型的医疗 Agent 评测口径。

## What Changes

按执行顺序：**P1-A**（A2/A3/B5/D/B2/A1）→ **P1-B**（B3/C4/高危/A6/C3）→ **P1-C**
（B1/C1-C2/C5/agent/扩库）→ **平台 P1-4/5**（主动 HITL + 校准 API）。

详见 `tasks.md`。
