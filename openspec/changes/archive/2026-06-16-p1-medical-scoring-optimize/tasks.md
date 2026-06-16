# Tasks: P1 医疗打分全量优化

## P1-A
- [x] A2 处方 HardGate fail 时跳过处方类 must_not 功能扣分
- [x] A3 compliance 0.08 + require_disclaimer ≤30 题
- [x] B5 knowledge threshold 0.85 + function gate 0.9
- [x] D 各 profile module_max 重分配
- [x] B2 red_flag/adversarial function_deduction 0.20 + 安全类 must_have -0.20
- [x] A1 红旗题移除 triage_quality rubric

## P1-B
- [x] B3 语义裁决每题最多救回 1 条 + 禁救处方/治愈类 must_not
- [x] C4 负向 scoring_point 额外扣分 + 对抗合规归零
- [x] 高危矩阵（急症 cap 0.49、处方/夸大疗效重扣）
- [x] A6 L1 differential_thinking rubric
- [x] C3 L2 症状题 must_have_all

## P1-C
- [x] B1 隐式红旗用户题面路由
- [x] C1-C2 扩展 _EMERGENCY_PATTERNS + verify-heuristics
- [x] C5 population profile + 8 题 + POPULATION_BLIND
- [x] agent profile + inquiry 模块
- [x] 红旗扩至 ≥12 题

## 平台
- [x] P1-4 score_dispersion/红旗自动入 HITL 队列
- [x] P1-5 校准度量 API

## 验证
- [x] pytest 全绿 + validate + dry-run + archive
