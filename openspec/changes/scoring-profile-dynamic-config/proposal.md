# Proposal: 评分场景动态配置（权重 / 扣分 / gates）

## Why

平台「阈值配置」仅覆盖 `min_composite`；运营需按 `score_profile` 调整模块权重、功能扣分步长与维度 gates，且仅对新评测/重判生效。

## What

- 扩展 `release_threshold_config` 表列（`module_max` / `function_deduction` / `safety_function_deduction` / `gates`）
- `GET/PUT /api/config/scoring-profiles`；保留 `/release-thresholds` 兼容
- `prepare_run_config` 合并 DB 覆盖到 `config.scoring`
- 前端「评分配置」Tab 表单（中文标签 + Tooltip）

## Scope

MUST：module_max、function_deduction、safety_function_deduction、min_composite、gates。  
NOT：grade_thresholds、thresholds.*、scoring 算法本身。
