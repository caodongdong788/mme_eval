# eval-platform-dashboard Specification (delta)

## ADDED Requirements

### Requirement: 看板进入默认概览与对话流水可滚动

从评测列表进入某个 run 看板时，平台 MUST 默认显示「概览」tab；仅当用户从「用例明细」打开的用例详情页点击「返回」时，MUST 落回「用例明细」tab。看板 tab 状态 MUST NOT 跨「从列表进入」复用上一次停留的 tab（即不得因 tab 记忆导致进入即停在非概览页）。用例筛选条件的记忆 MUST NOT 受影响。

用例详情页的「对话流水」MUST 限定一个固定高度，内容超出时 MUST 可上下滚动查看，且 MUST NOT 撑高整页布局。

#### Scenario: 从列表进入默认概览

- **WHEN** 用户在评测列表点击某个 run 的看板或名称
- **THEN** 看板 MUST 显示「概览」tab，而非上次停留的 tab

#### Scenario: 从用例详情返回落用例明细

- **WHEN** 用户从「用例明细」打开某用例详情后点击「返回」
- **THEN** 看板 MUST 落回「用例明细」tab

#### Scenario: 长对话可滚动

- **WHEN** 某用例对话流水很长、超出固定高度
- **THEN** 对话流水区 MUST 可上下滚动查看，整页布局 MUST NOT 被撑高

### Requirement: 用户登录信息置于右上角

平台 MUST 在页面右上角（顶部 header）展示当前登录用户信息与退出入口，MUST NOT 仍置于左侧导航栏底部。未登录时 MUST 不展示该入口。

#### Scenario: 右上角展示用户

- **WHEN** 用户已登录并进入平台任意页面
- **THEN** 右上角 MUST 展示用户名/头像与退出登录入口
