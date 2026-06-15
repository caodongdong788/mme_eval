import type { ThemeConfig } from "antd";

// 统一调色板（与 styles.css 的 CSS 变量镜像一致，禁止各页散落硬编码色值）。
// 设计语言：Ink & Whitespace —— 纯白底 / 无边框无阴影 / 大留白 / 圆点状态 / 降噪图表。
export const palette = {
  bg: "#FFFFFF",
  panel: "#FFFFFF",
  border: "#F3F4F6", // hairline（表格行底线）
  borderStrong: "#E5E7EB", // 输入/次按钮极细描边
  ink: "#111827",
  inkSecondary: "#374151",
  muted: "#9CA3AF",
  axis: "#D1D5DB",
  // 交互强调（唯一亮灯）：墨黑单色，去 teal（黑白印刷质感）
  primary: "#111827",
  primaryStrong: "#374151",
  primarySoft: "#F3F4F6",
  // 语义软色（仅作圆点 / 极小着色）
  pass: "#1F8A5B",
  warn: "#C6841F",
  fail: "#C1453A",
  // 图表配色：冷灰阶单色——主强调用墨黑，次级用深灰，去 teal
  chart: {
    teal: "#111827", // 主强调序列（墨黑，兼容旧 key 名）
    ink: "#6B7280", // 次级序列：与主强调拉开层次
    muted: "#9CA3AF",
    faint: "#E5E7EB",
    // 兼容旧引用（status 分布等场景仍可用语义色，但优先冷灰）
    tealSoft: "#9CA3AF",
    green: "#1F8A5B",
    amber: "#C6841F",
    red: "#C1453A",
    grid: "transparent",
    axis: "#D1D5DB",
  },
} as const;

const FONT_SANS =
  "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'SF Pro Display', 'Inter', 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif";

export const themeConfig: ThemeConfig = {
  token: {
    colorPrimary: palette.primary,
    colorPrimaryHover: palette.primaryStrong, // 黑底主按钮 hover 提亮为深灰
    colorPrimaryActive: "#000000",
    colorInfo: palette.primary,
    colorLink: palette.primary,
    colorLinkHover: palette.primaryStrong,
    colorSuccess: palette.pass,
    colorWarning: palette.warn,
    colorError: palette.fail,
    colorTextBase: palette.ink,
    colorBgLayout: palette.bg,
    colorBorder: palette.borderStrong,
    colorBorderSecondary: palette.border,
    colorSplit: palette.borderStrong, // 分割线（Divider/Descriptions/KPI 列）肉眼可辨的浅灰
    borderRadius: 8,
    fontFamily: FONT_SANS,
    fontSize: 15,
    controlHeight: 36,
    wireframe: false,
  },
  components: {
    Layout: {
      siderBg: palette.panel,
      headerBg: palette.panel,
      bodyBg: palette.bg,
      headerHeight: 56,
    },
    Menu: {
      itemBg: "transparent",
      subMenuItemBg: "transparent",
      itemSelectedBg: palette.primarySoft,
      itemSelectedColor: palette.primary,
      itemColor: palette.inkSecondary,
      itemHoverBg: "#FAFAFA",
      itemHeight: 38,
      itemMarginInline: 8,
      itemBorderRadius: 8,
      groupTitleColor: palette.muted,
      iconSize: 16,
    },
    Card: {
      borderRadiusLG: 12,
      colorBorderSecondary: "transparent",
      headerFontSize: 17,
      headerBg: "transparent",
      paddingLG: 24,
      boxShadowTertiary: "none",
    },
    Table: {
      headerBg: "transparent",
      headerColor: palette.muted,
      borderColor: palette.border,
      rowHoverBg: "#FAFAFA",
      cellPaddingBlock: 20,
      cellPaddingInline: 16,
      headerSplitColor: "transparent",
    },
    Button: {
      borderRadius: 8,
      // 次操作 = 幽灵/文本按钮：无边框无底色，hover 仅极浅灰底 + 字转墨黑。
      defaultBg: "transparent",
      defaultBorderColor: "transparent",
      defaultColor: palette.inkSecondary,
      defaultHoverBg: "#FAFAFA",
      defaultHoverColor: palette.primary,
      defaultHoverBorderColor: "transparent",
      defaultActiveBg: "#F3F4F6",
      defaultActiveColor: palette.primary,
      defaultActiveBorderColor: "transparent",
      paddingInline: 14,
    },
    Tag: {
      borderRadiusSM: 6,
    },
    Statistic: {
      contentFontSize: 28,
    },
    Segmented: {
      itemSelectedBg: palette.panel,
      trackBg: "#F3F4F6",
    },
    Tabs: {
      inkBarColor: palette.primary,
      itemSelectedColor: palette.ink,
      itemColor: palette.muted,
      titleFontSize: 15,
    },
  },
};
