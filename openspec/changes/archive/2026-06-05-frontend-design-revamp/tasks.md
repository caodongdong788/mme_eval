# Tasks

- [x] 1. 设计 token：`theme.ts`（antd 全局/组件 token，主色 #0E6E5C、圆角、字体栈）+ 全局 CSS（调色板 CSS 变量、字体）+ `main.tsx` 接入
- [x] 2. 应用骨架：`App.tsx` 浅色分组侧栏（评测/资源/操作）+ 顶部项目位 + 底部用户位 + 面包屑导航
- [x] 3. 看板 `RunDashboardPage`：页头 + 概览/用例明细/人工审核标签页 + KPI 瓦片 + 统一图表配色 + 软底淡色徽章明细表
- [x] 4. `RunsPage`：评测列表继承主题（状态徽章、进度、表格）
- [x] 5. `CaseDetailPage`：对话气泡流 + 判据明细 + HITL 裁定面板按新风格
- [x] 6. `BenchmarksPage`：用例模板下载按钮 + 列表 + 编辑模态继承主题
- [x] 7. `LaunchPage` / `TrendsPage`（图表配色）/ `LoginPage`（氛围版式）：按新设计 token 统一
- [x] 8. 验证：`tsc --noEmit` 通过 + `vite build` 通过 + 各页面浏览器视觉走查 + `graphify update .` + `openspec validate --strict` + archive
