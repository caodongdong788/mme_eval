# eval-platform-dashboard Specification (delta)

## ADDED Requirements

### Requirement: run 看板的重判 / 续跑 / 置顶操作

前端 run 看板 SHALL 提供「重判」「续跑」「置顶」操作入口：重判 / 续跑触发后端对应端点并在
成功后跳转到新产出的 run；置顶切换该 run 的保护状态并就地反映。当 run 不具备会话留痕
（`has_traces` 为假）时，重判 / 续跑入口 MUST 以禁用态或提示告知不可用，避免无效请求。

#### Scenario: 看板发起重判并跳转

- **WHEN** 用户在某成功 run 的看板点击「重判」
- **THEN** 前端调用重判端点，成功后跳转到新生成的 run 看板

#### Scenario: 不可重判时禁用入口

- **WHEN** 一个 run 的 `has_traces` 为假（无留痕，例如已被治理清理）
- **THEN** 看板的「重判 / 续跑」入口 MUST 不可用并给出原因提示
