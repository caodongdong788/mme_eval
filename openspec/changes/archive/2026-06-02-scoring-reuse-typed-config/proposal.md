## Why

`reporter/scoring.py`（四模块加权打分 + 评级 + `release_passed` 唯一赋值点）现在是 **"dict-in"**：吃 `RunReport.config_snapshot["scoring"]` 原始字典，用一长串 `cfg.get(...)` + 手写 `_normalize_pass_rule` **再解析一遍** scoring 配置。

而 `config.py` 已有同一份配置的强类型 schema（`ScoringCfg` / `ProfileCfg` / `WhenCfg` / `ProfileMatchCfg` / `ThresholdRule`，全 `extra="forbid"`）。结果是**同一份 scoring 配置被两套解析器解析两次**：加载期 `ScoringCfg` 校验一次，出报告期 `scoring.py` 又 dict-walk 一次。两边默认值、`pass_rule` 归一（`_normalize_pass_rule` vs `ThresholdRule`）可能悄悄漂移。

研发阶段，沿"单一解析真值源"主线收敛——让 `scoring.py` 在边界把 snapshot dict 解析成 `ScoringCfg` 再消费，删掉重复的 dict-walk / `_normalize_pass_rule`。

## What Changes

纯内部重构，**打分/评级/通过失败行为零变化**：

- `scoring.py` 在边界用 `ScoringCfg.model_validate(scoring_cfg or {})` 把传入的原始 dict 解析成 typed `ScoringCfg`，作为唯一解析入口。
- `resolve_profile` / `_when_matches` 改为读 typed 属性（`scfg.profile_match[i].when.tags_any` 等），不再 `cfg.get(...)`。
- 删除 `_normalize_pass_rule`：复用 `ScoringCfg`/`ProfileCfg` 已解析好的 `pass_rule`（`None | "perfect" | "threshold" | ThresholdRule`），由一个轻量 typed→归一 dict 适配承接。
- **保持公共契约不变**：`resolve_profile` 仍返回归一后的 `dict`（`pass_rule` 仍是 `{"type": ...}` 字典），`score_case` / `_evaluate_pass` / `apply_grading` / `grading_summary` 的签名与返回结构均不变，数值默认仍归 `scoring.py`（`DEFAULT_MODULE_MAX` 等）。

## Capabilities

### Modified Capabilities
- `reporting`：新增要求"报告层 scoring 配置解析必须复用 config 的 typed schema（单一解析真值源）"——禁止报告层另写一套 dict-walk/归一逻辑与加载期 schema 漂移；打分输出（维度分 / 综合分 / 评级 / `release_passed`）MUST 与重构前逐位一致。

## Impact

- 代码：仅 `medeval/reporter/scoring.py`；新增/补充 `tests/`（snapshot dict 走 ScoringCfg、pass_rule 三写法等价、行为对拍）。
- 行为：四模块分、综合分、评级、`release_passed`、扣分原因 / 高亮词、profile 解析**全部不变**；现有 `test_category_profiles` / `test_weighted_grading` / `test_clinical_benchmark_migration` 回归绿。
- 兼容性：`resolve_profile` 等公共函数签名与返回 shape 不变；`scoring.py` 仍接受原始 dict（内部解析），调用方（reporter aggregator / 测试）零改动。
- 依赖：`reporter/scoring.py → config.ScoringCfg` 单向依赖（无循环；config 不依赖 reporter）。
