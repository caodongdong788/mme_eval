# eval-platform-dashboard Specification (delta)

## ADDED Requirements

### Requirement: 得分点惩罚项清晰展示

用例详情「得分点」表 MUST 区分正分点与惩罚（负分）得分点。惩罚点 MUST NOT 显示无意义的 `0/0`：未触发时显示「未触发·罚则 -N」，已触发（出现被惩罚内容）时显示「已扣 -N」。说明 MUST 带出该点的符号与判据，使扣分性质一目了然。

#### Scenario: 惩罚点未触发

- **WHEN** 某负分得分点未触发（bot 未出现被惩罚内容）
- **THEN** 该行 MUST 显示为「未触发·罚则 -N」而非 `0/0`

### Requirement: 用例详情展示指南匹配率

用例详情 MUST 展示「指南匹配率」，以 `X%（matched/total）` 形式给出，其中 matched/total 为带指南锚点得分点的命中数与总数。当用例无带指南锚点的得分点时，MUST 显示「无指南锚点」而非 0%。

#### Scenario: 有指南锚点

- **WHEN** 用例存在带指南锚点的得分点且全部命中
- **THEN** 指南匹配率 MUST 显示为 `100%（n/n）`

### Requirement: 用例列表按指南匹配率过滤

用例列表 MUST 支持按指南匹配率过滤，至少提供「100%」「<100%」「无指南锚点」三档，服务端 MUST 按 `guideline_match_rate` 过滤（100%=匹配率为 1.0；<100%=非空且小于 1.0；无指南锚点=匹配率为空）。

#### Scenario: 过滤未满分

- **WHEN** 用户选择「<100%」过滤
- **THEN** 列表 MUST 只返回 `guideline_match_rate` 非空且小于 1.0 的用例
