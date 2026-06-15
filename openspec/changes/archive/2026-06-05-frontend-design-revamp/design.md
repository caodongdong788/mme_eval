# Design: 前端视觉体系（Langfuse/shadcn 风浅色设计系统）

## 设计目标与气质

医疗安全评测**观测平台**——气质应"临床级、可信、数据密集但克制"。借鉴 Langfuse 的 shadcn/ui 质感：
大量留白、超细边框、圆角卡片、等宽字呈现 ID/指标、软底淡色徽章、面积图迷你趋势、分组侧栏 +
面包屑/标签页导航。避免通用 AI 风（紫渐变、Inter、默认蓝、重阴影）。

## 技术路线（基于现有 antd5 + recharts，不引入 Tailwind）

不重写组件库，通过 **antd5 主题 token 定制 + 全局 CSS** 实现 shadcn 观感：

- `ConfigProvider.theme`：
  - 全局 token：`colorPrimary=#0E6E5C`、`borderRadius=8`、`fontFamily`（无衬线 UI 栈）、
    `colorBorderSecondary`（更淡）、`controlHeight`、`colorBgLayout` 近白。
  - 组件 token：`Table`（更紧凑行高、hairline 行分隔、hover）、`Tag`（软底淡色）、`Card`（细边框、
    弱阴影、圆角）、`Menu`（浅色、激活态左侧青绿指示）、`Layout`（浅色侧栏）、`Button`。
- 全局 CSS（新增 `frontend/src/index.css` 或 `styles.css`）：
  - CSS 变量沉淀调色板与间距：`--bg`、`--panel`、`--border`、`--ink`、`--muted`、`--primary`、
    语义色（pass/warn/fail 的 bg+text 软色对）、`--font-sans`、`--font-mono`。
  - 等宽字体类（ID/数值/延迟/时间戳）。
  - Web 字体：经 `index.html` 引入一套干净几何无衬线 + 等宽（如 Geist/Geist Mono 或同类开源字体，
    带 system 兜底）；中文走 system 思源/苹方兜底。
- 数据可视化（recharts）：统一配色（主色青绿 + 语义色），KPI 用淡色渐变 `AreaChart` 迷你趋势，
  图表去网格噪声、细线、克制。

## 调色板（CSS 变量）

| 变量 | 值 | 用途 |
| --- | --- | --- |
| `--bg` | `#FCFCFC` | 页面底 |
| `--panel` | `#FFFFFF` | 卡片/面板 |
| `--border` | `#EBEDEC` | 细边框 |
| `--ink` | `#18211E` | 主文本 |
| `--muted` | `#71807A` | 次要文本 |
| `--primary` | `#0E6E5C` | 主色（激活/强调/关键数值/迷你图） |
| pass | bg `#E7F4EE` / text `#1F7A52` | 通过 / 同意 |
| warn | bg `#FBF0DD` / text `#9A6516` | 待审 / 推翻 |
| fail | bg `#FBE9E7` / text `#B3352B` | 失败 |

## 布局骨架

- **侧栏**：浅色，顶部项目切换位（评测集/模型上下文），分组导航（评测：看板/评测列表/趋势；
  资源：Benchmark 库/用例模板；系统：发起评测/设置），底部用户位。激活项左侧青绿指示条。
- **内容头**：面包屑（评测 / <run 名>）+ 标签页（概览 / 用例明细 / 稳定性 / 人工审核）+ run 元信息
  等宽 chip 条 + 右侧操作（重判/续跑/置顶）。
- **KPI 行**：等宽大号数值 + 淡色面积图迷你趋势。
- **明细表**：等宽单元、hairline 行分隔、软底徽章、行 hover、失败行轻微红色高亮。

## 约束与非目标

- MUST 保持所有现有数据字段、API 调用、交互行为不变（仅呈现层改造）。
- MUST 不改后端、不改判分内核 `medeval/**`、不改 DB。
- MUST 不破坏既有功能：筛选记忆（sessionStorage）、失败标签中文映射、HITL 裁定、孤儿任务展示、
  benchmark 模板下载/重命名等保持可用。
- 非目标：暗色模式切换、移动端适配、组件库替换（留作后续）。

## 验证策略

前端无 pytest 单测，验证门为：`tsc --noEmit` 零错误 + `vite build` 成功 + 关键页面视觉走查
（侧栏/看板/明细/详情/benchmark）+ 确认既有交互未回归。
