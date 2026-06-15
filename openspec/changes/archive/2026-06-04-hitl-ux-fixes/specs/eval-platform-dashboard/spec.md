# eval-platform-dashboard Specification (delta)

## ADDED Requirements

### Requirement: 看板筛选记忆与失败标签中文化

看板"用例结果"区的筛选条件（上线判定 / Level / 稳定性 / 仅看待审）MUST 在用户跳转到用例详情页
并返回后保持不变，按 run 维度记忆（同一会话内）。失败标签在看板用例列、标签分布图与用例详情的
judge 判定中 MUST 渲染中文短标签（来自 `GET /api/config/failure-tags`），未知值 MUST 回退原始值。

#### Scenario: 返回看板保留筛选

- **WHEN** 用户在看板设置了筛选条件，点开某用例详情后点「返回看板」
- **THEN** 看板 MUST 恢复此前的筛选条件并据此展示用例列表

#### Scenario: 失败标签显示中文

- **WHEN** 用例存在失败标签（如 `missed_red_flag`）
- **THEN** 看板与详情页 MUST 显示其中文短标签，而非英文枚举值
