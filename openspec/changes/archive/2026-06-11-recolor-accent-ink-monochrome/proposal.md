# Proposal: 强调色由 teal 改为墨黑（纯黑白单色）

## Why

当前视觉契约把 teal `#0E6E5C` 定为「唯一亮灯」交互强调色（主按钮、链接、开关、选中 / 聚焦态、图表强调序列）。用户要求**彻底去绿、全站黑白极简**：发起评测页与列表页的绿色主按钮、绿色开关与界面里的 teal 都改成中性墨黑，使页面成为真正的黑白印刷品。

这是对单一信任源色板 token 的变更（`styles.css :root` + `theme.ts palette`），并相应更新设计契约 `DESIGN.md` / `.impeccable/design.json` 的「One Lamp」原则。

## What Changes

- 设计契约：`DESIGN.md` 与 `.impeccable/design.json` 的「唯一亮灯」由 teal 改为墨黑 ink `#111827`；移除 teal 命名色，新增 `chart-accent`。
- Token 镜像：`styles.css :root` 的 `--primary*` 与 `theme.ts` 的 `palette.primary*` / `colorPrimary` / `colorLink` / `palette.chart.*` 全部从 teal 改为墨黑单色（主强调 `#111827`、次级图表序列 `#6B7280`）。
- 主按钮：实底墨黑 + 白字，hover 提亮为深灰 `#374151`；链接墨黑、hover 加下划线保留可点可感。
- 图表强调序列由 teal 改为墨黑，次级序列用 `#6B7280` 与主强调拉开层次。
- 发起评测页 `LaunchPage` 与列表页统一组件风格（主按钮去 `large`、与列表页一致带图标）。
- 语义圆点 pass/warn/fail 保持不变（功能性状态色，不属品牌强调）。

## Impact

- Specs: `eval-platform-dashboard`（MODIFIED：看板视觉设计契约——强调色 teal→墨黑）。
- Docs: `DESIGN.md`、`.impeccable/design.json`。
- Code: `frontend/src/styles.css`、`frontend/src/theme.ts`、`frontend/src/pages/LaunchPage.tsx`（全站 `var(--primary)` / `palette.primary` 引用自动随 token 变色）。
- 行为：纯视觉变更，不改判分 / 数据逻辑。
