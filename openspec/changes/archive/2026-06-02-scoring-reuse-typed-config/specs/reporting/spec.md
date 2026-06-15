## ADDED Requirements

### Requirement: 报告层 scoring 配置解析必须复用 config 的 typed schema

报告层打分（`reporter/scoring.py`）对 scoring 配置的解析 MUST 复用 `config.py` 的 typed schema（`ScoringCfg` 及其子模型），作为单一解析真值源。报告层 MUST NOT 另写一套 dict-walk / `pass_rule` 归一逻辑，以免与加载期 schema 的默认值、字段集、`pass_rule` 解析口径漂移。

打分输出（四模块维度分、综合分、评级、`release_passed`、扣分原因、高亮词、profile 解析结果）MUST 与重构前逐位一致；`scoring.py` 对外仍接受原始 `dict`（在边界解析为 typed），公共函数签名与返回结构 MUST 保持不变。

#### Scenario: snapshot dict 经 typed schema 解析

- **当** `apply_grading` 收到 `config_snapshot["scoring"]`（dump 后的 ScoringCfg dict）
- **那么** 报告层 MUST 通过 `ScoringCfg` 解析后再消费，且打分结果与重构前一致

#### Scenario: pass_rule 三种写法归一一致

- **当** profile 的 `pass_rule` 为缺省 / 字符串（`perfect`|`threshold`）/ dict（`{type, min_composite, gates}`）
- **那么** 解析结果 MUST 等价于复用 typed schema 后的归一形态，profile 判定行为不变

#### Scenario: 非法 scoring 配置 fail-fast

- **当** 传入的 scoring 配置含拼错字段或 threshold 缺 `min_composite`
- **那么** 解析 MUST 经 `ScoringCfg` 即时报错，而非被静默忽略
