# Proposal: 前端视觉体系重构（Langfuse/shadcn 风浅色设计系统）

## Why

用户对现有前端 UI 不满意：当前为 antd 默认风（暗色侧栏 + 默认蓝主色 + 默认圆角/字体/Tag），
视觉零定制、层次平、气质与"医疗安全评测观测平台"的定位不匹配。经设计稿对比，用户选定一套
**Langfuse / shadcn 风的浅色设计系统**：克制中性灰 + 临床青绿主色（#0E6E5C）、细边框圆角卡片、
等宽字体呈现 ID/指标/延迟、软底淡色状态徽章、面积图迷你趋势、分组侧栏 + 面包屑/标签页导航。

本次为**纯前端视觉/交互体系重构**，建立统一设计 token 并逐页落地，不改后端契约、不改 API 形状、
不触判分内核 `medeval/**`。

## What Changes

- **设计 token 体系**：通过 antd5 `ConfigProvider.theme`（全局 token + 组件 token）统一主色、圆角、
  字体、边框、控件高度；新增全局 CSS 与 Web 字体（无衬线 UI 字体 + 等宽字体）。MUST 用 CSS 变量沉淀
  调色板与间距，禁止散落硬编码色值。
- **应用骨架（App.tsx）**：暗色侧栏 → **浅色分组侧栏**（评测/资源/系统分组 + 顶部项目位 + 底部用户位）；
  内容区引入**面包屑 + 标签页**导航骨架。
- **单次看板（RunDashboardPage）**：KPI 卡改为「标签 + 大号数值 + 淡色面积图迷你趋势」；图表精简、统一
  配色；筛选条独立成行（评级/上线判定/失败标签/搜索 + 导出）；明细表用**软底淡色徽章**药丸。
- **全量页面统一**：RunsPage / CaseDetailPage（含 HITL 裁定面板）/ BenchmarksPage / LaunchPage /
  TrendsPage / LoginPage 全部按新设计 token 与组件规范重排。
- **语义色约定**：通过(绿) / 失败(红) / 待审(琥珀) / 同意(绿) / 推翻(琥珀)，MUST 用软底淡色（低饱和），
  仅状态语义使用，主色青绿仅用于强调/激活/关键数值与迷你图。

## Impact

- Affected specs: `eval-platform-dashboard`。
- Affected code: `frontend/src/**`（`main.tsx`、`App.tsx`、`pages/*`、新增 `theme.ts` / 全局 css）。纯前端。
- 后端契约、API 形状、判分内核 `medeval/**` 与数据库 **零改动**；所有现有数据字段与交互行为保持不变，
  仅视觉/布局/组件呈现优化。
