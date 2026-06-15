# Tasks: 前端视觉系统重构（极致留白 / 杂志级排版）

## 1. 设计契约（先行）

- [ ] 1.1 重写 `DESIGN.md`：Overview/Colors/Typography/Elevation/Components/Do's&Don'ts 切到新语言
- [ ] 1.2 同步 `.impeccable/design.json`（colorMeta / typographyMeta / shadows / narrative）
- [ ] 1.3 `frontend-workflow.mdc` §1 设计漂移注记（指向本 change）

## 2. Token + AntD 主题（单一信任源镜像）

- [ ] 2.1 `styles.css :root`：纯白底、近黑墨、浅灰、发丝行线；font-sans 系统优先；保留 teal & mono
- [ ] 2.2 `theme.ts palette` 同步镜像；AntD Card/Table/Tag/Layout/Button 去边框去阴影、表格去网格
- [ ] 2.3 全局类：状态圆点 `.status-dot`、大指标 `.kpi-value`、杂志级表格、去边框卡片

## 3. 共享组件

- [ ] 3.1 `KpiTile.tsx`：大字号系统无衬线指标 + 浅灰标签
- [ ] 3.2 `RunStatusTag.tsx` / `caseColumns.tsx`：彩色 Tag → 圆点 + 文字
- [ ] 3.3 `MetaChip.tsx`：去底色去边框（留白/分隔点）
- [ ] 3.4 图表 helper：统一 Recharts 降噪配置（无网格、隐藏轴线、冷灰 + teal）

## 4. 页面铺开（14 页）

- [ ] 4.1 `RunDashboardPage` + `RunOverviewTab`（主战场：大指标 + 图表 + 表格）
- [ ] 4.2 `CaseDetailPage` / `PairwiseDetailPage`（硬编码最多）
- [ ] 4.3 `RunsPage` / `TrendsPage` / `PairwisePage` / `LaunchPage`
- [ ] 4.4 `BenchmarksPage` / `JudgeModelsPage` / `ReleaseThresholdsPage` / `LoginPage`
- [ ] 4.5 Modal/Drawer 组件（RejudgeModal / ExportTranscriptsModal / EditCriteriaDrawer / PairwiseCalibrateModal）

## 5. 验证（自审清单）

- [ ] 5.1 `cd frontend && npm run typecheck` 通过
- [ ] 5.2 裸 hex 扫描无输出：`rg '#[0-9A-Fa-f]{3,8}' frontend/src --glob '!styles.css' --glob '!theme.ts'`
- [ ] 5.3 `npm run build` 通过
- [ ] 5.4 frontend-workflow §4 自审清单逐条过
- [ ] 5.5 `graphify update .` + 归档
