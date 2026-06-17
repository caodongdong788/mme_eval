---
name: MME · Agent 评测平台
description: 一套面向内部医疗 chatbot 评测的「极致留白 / 杂志级排版」视觉系统——纯白底、无边框无阴影、超大核心指标、黑白印刷质感、圆点状态、降噪图表；墨黑 ink 主操作 + Muted Teal 导航链接（双灯规则）。
colors:
  primary: "#111827"
  primary-soft: "#F3F4F6"
  link: "#0D6B5C"
  link-hover: "#0A5549"
  link-tint: "rgba(13, 107, 92, 0.06)"
  ink: "#111827"
  ink-secondary: "#374151"
  muted: "#9CA3AF"
  bg: "#FFFFFF"
  panel: "#FFFFFF"
  hairline: "#F3F4F6"
  hairline-strong: "#E5E7EB"
  axis: "#D1D5DB"
  pass: "#1F8A5B"
  warn: "#C6841F"
  fail: "#C1453A"
  chart-ink: "#374151"
  chart-muted: "#9CA3AF"
  chart-faint: "#E5E7EB"
  chart-accent: "#111827"
  on-primary: "#FFFFFF"
typography:
  metric-hero:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', 'Segoe UI', Roboto, 'PingFang SC', sans-serif"
    fontSize: "40px"
    fontWeight: 400
    lineHeight: 1.05
    letterSpacing: "-0.015em"
    color: "{colors.ink}"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', 'Segoe UI', Roboto, 'PingFang SC', sans-serif"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  heading:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', 'Segoe UI', Roboto, 'PingFang SC', sans-serif"
    fontSize: "17px"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', 'Segoe UI', Roboto, 'PingFang SC', sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.6
  caption:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', 'Segoe UI', Roboto, 'PingFang SC', sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
    color: "{colors.muted}"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', 'Segoe UI', Roboto, sans-serif"
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1.0
    letterSpacing: "0.08em"
    color: "{colors.muted}"
  mono:
    fontFamily: "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "'tnum' 1, 'cv01' 1"
rounded:
  xs: "6px"
  sm: "8px"
  md: "10px"
  lg: "12px"
  xl: "16px"
  pill: "9999px"
spacing:
  xxs: "4px"
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  xxl: "48px"
  section: "64px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.sm}"
    height: "36px"
    padding: "0 18px"
  button-default:
    backgroundColor: "transparent"
    textColor: "{colors.ink-secondary}"
    border: "none"
    hoverBackground: "#FAFAFA"
    hoverTextColor: "{colors.primary}"
    rounded: "{rounded.sm}"
    height: "36px"
    padding: "0 14px"
  card:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    border: "none"
    boxShadow: "none"
    padding: "0"
  kpi-hero:
    label: "{typography.caption}"
    value: "{typography.metric-hero}"
  table:
    headerBackground: "transparent"
    headerColor: "{colors.muted}"
    rowSeparator: "1px solid {colors.hairline}"
    verticalGrid: "none"
    zebra: "none"
    cellPaddingBlock: "18px"
  status-dot:
    size: "6px"
    rounded: "{rounded.pill}"
    textColor: "{colors.ink-secondary}"
  chip:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    typography: "{typography.mono}"
    padding: "0"
---

# Design System: MME · Agent 评测平台

## 1. Overview

**Creative North Star: Dashboard Surface（全站统一）**

平台采用 Coze 风 **Dashboard Surface**：浅灰底 `#F3F4F8`、白卡片（圆角 12px + 轻阴影）、紫色 `#7C5CFC` 作 Tab / 主按钮 / 表格链接 / 侧栏选中 / 图表强调。覆盖侧栏、所有列表/表单页、Run 看板、用例钻取、Pairwise 对比详情。

**Key Characteristics:**
- 浅灰画布 + 白卡片 + 轻阴影；紫色强调、Teal 作次要图表序列。
- 侧栏白底、紫色选中项、品牌标紫渐变。
- 表格灰表头 `#FAFBFC`、紫链接、pill 圆角筛选条。
- KPI 白卡网格；状态仍用 6px 圆点 + 文字。
- 表内数字 JetBrains Mono + tnum。
- 正文导航链（面包屑 / 表内链）紫色；外链仍附 ↗。

## 2. Colors

纯粹的黑白印刷纸面为底，靠字重、留白与对比说话；导航链接单独用低饱和 Teal 提升可发现性。

### Primary（主操作 = 墨黑）
- **Ink Accent**（`{colors.primary}` · #111827）：主按钮（实底黑 + 白字）、聚焦环、图表主强调序列。覆盖率极低。
- **Ink Wash**（`{colors.primary-soft}` · #F3F4F6）：极浅中性灰，用于 hover 等极少量轻填充。

### Link（导航 = Muted Teal）
- **Link**（`{colors.link}` · #0D6B5C）：正文内链、操作型链接（`Button type="link"`）、面包屑跳转。默认下划线，`text-underline-offset` 3px。
- **Link Hover**（`{colors.link-hover}` · #0A5549）：链接 hover 色。
- **Link Tint**（`{colors.link-tint}` · rgba(13,107,92,0.06)）：侧栏选中项极淡底。
- **外链**：`target="_blank"` 在主内容区自动附 ↗；侧栏 Menu 无下划线、无 Teal。

### Neutral（黑白印刷骨架）
- **Ink**（`{colors.ink}` · #111827）：近黑墨色，承载标题、核心指标与正文主字。
- **Ink Secondary**（`{colors.ink-secondary}` · #374151）：状态文本、表格正文、次级标题。
- **Muted**（`{colors.muted}` · #9CA3AF）：副标题、单位、说明、表头、坐标轴文字、占位。
- **Paper**（`{colors.bg}` = `{colors.panel}` · #FFFFFF）：唯一底面，纯白，无灰底分区。
- **Hairline**（`{colors.hairline}` · #F3F4F6）：**唯一允许的分隔线**——表格行底线。比它更重的横线一律不用。
- **Hairline Strong**（`{colors.hairline-strong}` · #E5E7EB）：极克制地用于输入框 / 次按钮描边，别处不用。
- **Axis**（`{colors.axis}` · #D1D5DB）：图表轴线（通常隐藏）/ 极弱参考线。

### 语义色（仅作圆点）
- **Pass** `{colors.pass}` #1F8A5B / **Warn** `{colors.warn}` #C6841F / **Fail** `{colors.fail}` #C1453A：**不再做面状标签**，只作 6px 圆点；旁边的状态文字用 `{colors.ink-secondary}`。

### Chart 灰阶
- **Chart Accent / Ink / Muted / Faint**（#111827 / #6B7280 / #9CA3AF / #E5E7EB）：图表全冷灰阶单色——主强调序列用墨黑 #111827，次级序列用 #6B7280 与之拉开层次（去 teal）。

### Named Rules
**The Dashboard-Everywhere Rule（全站 Dashboard）.** 侧栏、主内容、用例钻取、资源与对比页 MUST 同一套灰底 + 白卡 + 紫强调，禁止在同一产品内混用「无边框杂志表」与「灰表头白卡表」。

**The Purple-Lamp Rule（紫色强调）.** 紫色管主按钮 / Tab / 侧栏选中 / 表格链接 / 面包屑；状态圆点仍用 pass/warn/fail 语义色。

**The Status-Not-Just-Color Rule（状态不靠纯色）.** 通过 / 失败 / 稳定性 / 红旗等状态**必须**同时带文字（圆点 + 深灰文字），绝不只靠红绿圆点区分。

**The Ink & Paper Rule（墨与纸）.** 除语义圆点（pass/warn/fail）与导航链接色外，全页只有近黑 / 深灰 / 浅灰 / 纯白。**禁止**面状彩色填充（标签、徽章、色块背景）。

## 3. Typography

**UI / Body Font:** 系统无衬线优先栈 `-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif`——Apple / Dieter Rams 式的中性、克制、即取即用。
**Metric / Mono Font:** JetBrains Mono（`ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`），开启 `'tnum' 1, 'cv01' 1`。

**Character:** 整套排版靠**字号的极致对比**说话——顶部综合分 / 通过率是 52px 的杂志大标题，副信息缩到 13px 浅灰。正文与界面统一用系统无衬线（不再用 Manrope），让页面像 macOS 原生应用一样安静；而**表格内的 ID、指纹、分数列、token / 成本数字仍用 JetBrains Mono + tnum**，保证逐列对齐——这是仪器精度的底线。

### Hierarchy
- **Metric Hero**（`{typography.metric-hero}` · 系统无衬线 40px / 400 / -0.015em）：顶部概览主指标（综合分、通过率）。大而轻盈、单行呈现，不压成黑体。
- **Title**（`{typography.title}` · 28px / 600）：页面 / run 主标题。
- **Heading**（`{typography.heading}` · 17px / 600）：区块标题。
- **Body**（`{typography.body}` · 15px / 400 / 1.6）：默认正文、表格单元、表单。
- **Caption**（`{typography.caption}` · 13px / 400 / muted）：KPI 标签、单位、次要说明、表头。
- **Label**（`{typography.label}` · 11px / 600 / 0.08em / 大写 / muted）：侧栏分组等克制全大写微标签。
- **Mono**（`{typography.mono}` · JetBrains Mono 12.5px / tnum）：ID、指纹、表格数字列、成本数值。

### Named Rules
**The Scale-Contrast Rule（极致对比）.** 核心指标与其标签 / 单位之间用 ~3× 字号差（40px ↔ 13px）拉开层级，**禁止**用边框或色块再去强调——对比本身就是层级。

**The Numerals-In-Tables-Are-Mono Rule（表内数字等宽）.** 表格列里的指标 / 分数 / ID / token / 成本数值**必须**用 JetBrains Mono + tnum 保对齐；顶部 Hero 大指标用系统无衬线 Semibold。

## 4. Elevation

系统是**绝对平的**：没有卡片边框、没有卡片阴影、没有灰底分区。深度**只来自留白**——区块之间用 48–64px 的大间距呼吸，而非任何描边或投影。

唯一例外：真正「浮」在页面之上的浮层（Modal / Dropdown / 登录卡）允许一层柔和阴影做层级分离；表格行允许 1px `{colors.hairline}` 底线分行。

### Shadow Vocabulary
- **Flat（默认）**：`box-shadow: none`，卡片 / KPI / 区块一律无阴影无边框。
- **Float overlay**（`box-shadow: 0 16px 48px rgba(17, 24, 39, 0.10)`）：Modal / Dropdown / 登录卡等浮层。

### Named Rules
**The Whitespace-First Rule（留白优先）.** 层级**只**用留白与字号对比表达。**禁止**给卡片 / KPI / 区块 / 按钮 / 标签 / 表格行加边框或阴影（表格行底发丝线与浮层阴影除外）。如果它看起来像一张「卡片」，说明边框 / 阴影该去掉、留白该加大。

## 5. Components

### Buttons
- **Shape:** 圆角 `{rounded.sm}`（8px），高度 36px。
- **Primary:** 墨黑 `{colors.primary}`（#111827）实底 + 白字，承载主操作（发起评测、确认）。这是页面唯一的实底按钮，hover 提亮为深灰 `{colors.ink-secondary}`。
- **Default（次操作 · 幽灵/文本按钮）:** 透明底 + **无边框** + `{colors.ink-secondary}` 字；hover 仅加极浅灰底 `#FAFAFA` + 字转墨黑。重判 / 续跑 / 导出 / 编辑判据 / 置顶等次操作一律用它——靠留白与 hover 反馈表达可点，不靠描边盒子。**不**做位移 / 弹跳动效。
- **Danger（删除类）:** 同幽灵形态，字用 `{colors.fail}`，hover 极浅红底。

### KPI / 核心指标
- 无瓦片、无底色：仅**标签（Caption 浅灰）在上、Hero 大数字（40px 近黑 Regular）在下**，单行呈现。失败 / 警示态用数字旁的小圆点或墨黑着色，不加色块。
- **列间分隔（留白优先的明确例外）**：同一行的 KPI 之间用 1px `{colors.hairline-strong}`（#E5E7EB）竖发丝线分区——比表格行线 `#F3F4F6` 略深、肉眼可辨；首列不加线。这是杂志式分栏的克制处理，**不是**回到卡片描边。

### Status（圆点制）
- 通过 / 失败 / 稳定 / 抖动等：**6px 纯色圆点 + 深灰文字**。pass 绿点、fail 红点、warn 琥珀点、运行中墨黑点、等待中浅灰点。文字始终在，绝不只靠圆点颜色。

### Tables（签名组件 · 杂志级）
- 无边框、无竖网格线、无斑马纹、无表头底色。
- 表头：透明底 + Caption 浅灰小字 + 0.04em 字距，与正文拉开层次。
- 行分隔：仅 1px `{colors.hairline}` 底线（或纯靠行距留白）。
- 单元呼吸：大纵向内边距（`cellPaddingBlock` 20px，等价 AntD `size="large"` 的呼吸感），阅读如杂志正文。
- 数字列一律 Mono + tnum 右/左对齐保列齐。

### Dividers
- 优先用留白（`margin` 24–32px）代替分割线；必须分隔时用 1px `{colors.hairline}`（#F3F4F6）极浅线，绝不用更重的描边。

### Cards / Containers
- **不是卡片**：透明底、无边框、无阴影、无圆角包裹；区块靠 48–64px 留白与标题分区。需要分组时用标题 + 留白，不用描边盒子。

### Inputs / Fields
- 白底 + 1px `{colors.hairline-strong}` 极细描边 + 圆角 8px + 高 36px；墨黑聚焦环，不发光不位移。

### Navigation
- Sider / Header：纯白底，仅 1px `{colors.hairline}` 分隔；header 高 56px。
- Menu：选中项 Ink Wash 浅灰底 + 墨黑字 + 8px 圆角；未选中 `{colors.ink-secondary}`、无下划线，hover 极浅灰底；分组标题用 Label；**不受 Link Teal 规则影响**。

### 评测列表页（Runs · Coze 风概览区）
- **范围**：仅 `/runs` 主内容区（`.dash-page` / `.runs-page`）；**侧栏保持 Ink & Whitespace**。
- **表面**：浅灰底 `#F3F4F8` + 白卡片圆角 12px + 轻阴影；强调色 `#7C5CFC`（紫）用于 Tab 选中、主按钮、图表、表格链接。
- **结构**：顶栏 KPI 四卡 → 筛选 Tab → 通过率趋势图 → 双列副图 → 评测记录表。
- **Token**：`theme.ts` → `palette.dashboard` 与 `styles.css` → `--runs-*` / `--dash-*` 镜像。

### Dashboard Surface（全站统一）
- **范围**：侧栏 + 顶栏 + **所有**路由主内容（评测 / 资源 / 对比 / 用例钻取）。
- **页面壳**：`DashboardPageShell` 或 `.dash-page`；详情分区用 `DashPanel`（`.dash-panel`）。
- **侧栏**：白底、紫渐变品牌标、Menu 选中 `purpleSoft` + 紫字。
- **表格**：`.dash-table-card` / `.dash-panel` + `.dash-table`；操作列用 `DashTableActions` + `DashTableLink`（紫）/ `DashTableDangerLink`（红）。
- **筛选**：`.case-toolbar.dash-filter-bar` pill Select；profile 标签用 `.dash-chip`。
- **Token**：`palette.dashboard` ↔ `--runs-*` / `--dash-*`。

### Run 看板 · 概览 Tab
- **范围**：`.run-overview-page`（`/runs/:id` 概览 Tab 内容区）；侧栏与页头（RunDashboardHeader）保持原风格。
- **结构**：6 项 KPI 白卡 → 延迟/Token 双卡 → 三列图表（分层级、四模块、失败标签）。
- **图表色**：紫柱 + Teal 折线 / 饼图，与评测列表共用 `palette.dashboard`。
- 品牌标记：30×30 圆角方块，墨黑渐变（#111827 → #374151，去 teal）。

### Charts（Recharts · 降噪）
- 关闭所有 `splitLine`（无网格）；隐藏 `axisLine` / `tickLine`，仅留浅灰 `{colors.muted}` 轴文字。
- 线 / 柱调细、留白充足；配色走冷灰阶（`{colors.chart-ink}` / `{colors.chart-muted}` / `{colors.chart-faint}`）+ 单一墨黑 `{colors.chart-accent}` 强调序列（去 teal）。**禁止**大面积高饱和色块。

## 6. Do's and Don'ts

### Do:
- **Do** 用留白与字号对比（52px ↔ 13px）表达层级，区块间 48–64px 呼吸。
- **Do** 纯白底，全页黑白印刷为底；墨黑管主操作，Muted Teal 管导航链接（默认下划线）。
- **Do** 状态用 6px 圆点 + 深灰文字（保留文字，兼顾色觉差异）。
- **Do** 表格无竖线 / 无斑马 / 无表头底色，仅水平发丝线 + 大单元内边距。
- **Do** 图表关网格、隐藏轴线、调细线柱、冷灰 + 单一墨黑强调。
- **Do** 表内 ID / 分数 / 数字列用 JetBrains Mono + tnum；Hero 大指标用系统无衬线 Semibold。

### Don't:
- **Don't** 给卡片 / KPI / 区块 / 按钮 / 标签 / 表格行加边框或阴影（行底发丝线、浮层阴影除外）。
- **Don't** 用面状彩色 Tag / Badge / 色块背景表达状态或分类。
- **Don't** 用灰底分区或竖网格线切割内容——用留白。
- **Don't** 让链接与正文同色且无下划线（不可发现）。
- **Don't** 引入大面积品牌色块或渐变。
- **Don't** 做花哨营销落地页 / 老旧医院系统 / 玩具化 / 大屏炫技（呼应 PRODUCT.md anti-reference）。
- **Don't** 用纯红绿圆点而不配文字；**Don't** 把表内数字用比例字体破坏列对齐。

## 7. Governance（规范与门禁）

设计与实现通过以下链路互引，**改色板须四处同步**（`DESIGN.md` → `.impeccable/design.json` → `frontend/src/styles.css` → `frontend/src/theme.ts`）。

| 文档 / 代码 | 角色 |
|-------------|------|
| `PRODUCT.md` | 战略、anti-reference 红线 |
| 本文件 `DESIGN.md` | 视觉命名规则、Dashboard / Ink 双灯 |
| `.cursor/rules/frontend-workflow.mdc` | 开发五步流程、目录分层、组件硬规则 |
| `frontend/src/styles.css` | CSS token 单一源（`:root` + `--runs-*`） |
| `frontend/src/theme.ts` | JS token 镜像（`palette` / `palette.dashboard`） |
| `frontend/src/labels.ts` | 领域中文标签；`PROFILE_LABEL` 与 `server/services/platform_config.PROFILE_LABELS_ZH` 同步 |

**自动门禁**（触达 `frontend/**` 变更后 MUST 全绿）：

```bash
cd frontend && npm run verify
# 或仓库根：scripts/verify_frontend.sh
```

`check:standards` 校验：散落 hex、禁止第二 UI 框架、`pages/` 分层、`styles.css`↔`theme.ts` 镜像、`PROFILE_LABEL` 前后端一致。详见 `frontend-workflow.mdc` §5。
