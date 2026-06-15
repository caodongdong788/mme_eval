# Proposal: 看板 tab 默认概览修复 + 对话流水可滚动 + 用户登录移至右上角

## Why

平台三处前端体验问题：

1. **tab 缓存 bug**：从「评测列表」点击看板/名称进入某个 run，应默认落「概览」，但当前会恢复上次停留的 tab（sessionStorage 记忆），不符合预期。
2. 用例明细的「对话流水」不限高，长对话把页面撑得很长，难以浏览。
3. 用户登录信息当前在左侧栏底部，期望放到右上角。

## What Changes

- 进入 run 看板 MUST 默认显示「概览」tab；仅当从「用例明细」的用例详情页点「返回」时 MUST 落回「用例明细」tab。改用路由 `state` 传递返回意图，移除导致 bug 的 sessionStorage tab 记忆（用例筛选记忆不受影响）。
- 用例明细「对话流水」MUST 限定一个合理的固定高度，超出部分 MUST 可上下滚动查看。
- 用户登录信息 MUST 展示在右上角（顶部 header），不再置于左侧栏底部。

## Impact

- Affected specs: `eval-platform-dashboard`。
- Affected code（纯前端）：
  - `frontend/src/pages/RunDashboardPage.tsx`：tab 初值改为读路由 state、默认 `overview`，移除 sessionStorage tab 读写。
  - `frontend/src/pages/CaseDetailPage.tsx`：返回链接改用 `state={{ tab: "detail" }}`；对话流水容器加固定高度 + 滚动。
  - `frontend/src/App.tsx`：`UserBar` 从 `Sider` 移到 `Layout.Header` 右侧。
  - `frontend/src/styles.css`：header 用户位样式。
- 判分内核与后端零改动。
