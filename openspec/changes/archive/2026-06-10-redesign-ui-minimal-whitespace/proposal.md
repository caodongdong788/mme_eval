# Proposal: 前端视觉系统重构 —— 极致留白 / 杂志级排版

## Why

现行「Clinical Instrument」视觉系统以发丝边框 + 微光阴影 + 灰底表面微差建立层级。
产品方希望切换到「极致留白 + 大字号（Apple / Dieter Rams）+ Bauhaus 极简」的语言：
纯白底、无卡片边框/阴影、夸张留白分区、超大核心指标、黑白印刷质感、圆点状态、降噪图表。
这是一次**根本性设计漂移**，按 `.cursor/rules/frontend-workflow.mdc` §1 必须先更新设计契约
（`DESIGN.md` + `.impeccable/design.json`）再改代码，并先有计划。

## What Changes

- **设计契约**：重写 `DESIGN.md` 与 `.impeccable/design.json` 为新语言（保留 teal「唯一亮灯」
  与「状态带文字」无障碍硬线；推翻「发丝优先 + 微光阴影」改为「留白优先 + 无边框无阴影」；
  大指标改系统无衬线，表内 ID/列数字仍用 mono 保对齐）。
- **Token（单一信任源镜像）**：`styles.css :root` 与 `theme.ts palette` 同步——底色纯白
  `#FFFFFF`、墨色近黑 `#111827`、辅助浅灰 `#9CA3AF`、行分隔发丝 `#F3F4F6`、teal 保留为交互色。
- **AntD 主题**：Card 去边框去阴影；Table 去竖网格/斑马纹、表头无底色小灰字、行底发丝线、加大单元
  内边距；Layout 纯白；Tag 多数场景改为「圆点 + 深色文字」。
- **核心指标**：顶部概览数字 48–56px、Semibold、纯黑、系统无衬线；辅助文字 12–14px 浅灰。
- **状态**：彩色面状 Tag → 6px 纯色圆点 + 深灰/黑文字（保留文字，满足色觉无障碍）。
- **图表（Recharts）**：关 splitLine、隐藏轴线/刻度、轴文字浅灰、线/柱调细、冷灰低饱和单色 +
  teal 单一强调序列。
- **页面铺开**：全部 14 页 + 6 复用组件按新系统覆写。

## Impact

- Affected specs: 无（纯表现层重构，不改任何后端契约 / 数据模型 / API）。
- Affected docs: `DESIGN.md`、`.impeccable/design.json`、`frontend-workflow.mdc`（同步设计漂移注释）。
- Affected code: `frontend/src/styles.css`、`theme.ts`，`components/*`，`pages/*`（全量）。
- 不动后端、不引入第二个 UI/CSS 库（仍 AntD 单库）、不散落裸 hex（token 单一源）。
