# Proposal: agent 用例 + population_blind 标签 emit

## Why

P1 遗留：`agent` profile 无对应用例；`population` 题 rule 失败未 emit `POPULATION_BLIND`，失败归因不可用。

## What Changes

1. 新增 `cases/breast_cancer/agent.yaml`（4 道多轮 `score_profile: agent` 题）。
2. `RuleJudge`：population profile 且 `must_have` fail 时 emit `FailureTag.POPULATION_BLIND`。
3. 更新 `FailureTag.POPULATION_BLIND` 描述（去掉 reserved 占位）。
