## ADDED Requirements

### Requirement: 看板视觉设计契约（Ink & Whitespace）

前端看板 SHALL 遵循 `DESIGN.md` 的「The Clinical Instrument — Ink & Whitespace」视觉契约，并以
`frontend/src/styles.css` 的 `:root` 变量与 `frontend/src/theme.ts` 的 `palette` 为**镜像一致的
单一信任源**。具体约束：

- 底面 MUST 为纯白 `#FFFFFF`；卡片 / KPI / 区块 MUST NOT 带可见边框或卡片阴影，模块区隔
  MUST 仅依靠留白（浮层 Modal/Dropdown/登录卡的柔和阴影、表格行底 1px 发丝线除外）。
- 顶部核心指标 MUST 用系统无衬线 Semibold 大字号（≈52px）+ 近黑 `#111827`；辅助文字 MUST 用
  小字号浅灰 `#9CA3AF`。
- 状态指示 MUST 用 6px 纯色圆点 + 深灰文字，MUST NOT 用面状彩色 Tag/Badge；状态 MUST 始终保留
  文字标签（不只靠颜色，兼顾色觉无障碍）。
- 数据表格 MUST 去竖网格线 / 去斑马纹 / 去表头底色，仅保留 1px 发丝水平行线并加大单元内边距。
- 图表 MUST 关闭背景网格线、隐藏轴线 / 刻度线（仅留浅灰轴文字）、调细线柱，配色 MUST 为冷灰阶 +
  单一 teal 强调序列。
- teal `#0E6E5C` MUST 为唯一品牌交互色（链接 / 主按钮 / 选中 / 聚焦 / 图表强调）；MUST NOT 引入第二
  个品牌强调色。表内 ID / 分数 / 数字列 MUST 用 JetBrains Mono + `tnum` 保对齐。

#### Scenario: 单次评测看板呈现核心指标与状态

- **WHEN** 用户打开某次成功 run 的看板
- **THEN** 顶部综合分 / 通过率以 ≈52px 近黑系统无衬线大字呈现、副信息为浅灰小字
- **AND** 用例表无竖网格线 / 无斑马纹 / 无表头底色、仅水平发丝行线
- **AND** 「上线判定 / 稳定性 / 运行状态」等以 6px 圆点 + 深灰文字呈现，绝不只靠红绿色块

#### Scenario: 图表降噪渲染

- **WHEN** 看板渲染分层级 / 四模块 / 趋势等图表
- **THEN** 图表 MUST NOT 显示背景网格线与坐标轴实线 / 刻度线，仅保留浅灰轴文字
- **AND** 线 / 柱为细描边、冷灰阶 + 单一 teal 强调，无大面积高饱和色块
