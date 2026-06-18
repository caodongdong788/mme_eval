import type { ThemeConfig } from "antd";

// 统一调色板（与 styles.css CSS 变量镜像；禁止业务代码散落 hex）。
// Ink 层 + palette.dashboard（--runs-*）；门禁：npm run check:standards · 规范：frontend-workflow.mdc
export const palette = {
  bg: "#FFFFFF",
  panel: "#FFFFFF",
  border: "#F3F4F6", // hairline（表格行底线）
  borderStrong: "#E5E7EB", // 输入/次按钮极细描边
  ink: "#111827",
  inkSecondary: "#374151",
  muted: "#9CA3AF",
  axis: "#D1D5DB",
  // 交互强调：墨黑主操作 + Muted Teal 导航链接（双灯规则，见 DESIGN.md）
  primary: "#111827",
  primaryStrong: "#374151",
  primarySoft: "#F3F4F6",
  link: "#0D6B5C",
  linkHover: "#0A5549",
  linkTint: "rgba(13, 107, 92, 0.06)",
  // 评测列表概览（Coze 风卡片区，不影响侧栏）
  dashboard: {
    bg: "#F3F4F8",
    card: "#FFFFFF",
    text: "#1F2329",
    textSecondary: "#646A73",
    textMuted: "#8F959E",
    border: "#E8EAED",
    purple: "#7C5CFC",
    purpleSoft: "#F3F0FF",
    purpleLine: "#9B8AFB",
    teal: "#2DB88A",
    tealSoft: "#E8F8F1",
    red: "#F54A45",
    redSoft: "#FDEEED",
    shadow: "0 1px 2px rgba(31, 35, 41, 0.04), 0 4px 16px rgba(31, 35, 41, 0.06)",
  },
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

export const dashboardPieColors = [
  palette.dashboard.purple,
  palette.dashboard.purpleLine,
  palette.dashboard.teal,
  palette.dashboard.textMuted,
] as const;

const FONT_SANS =
  "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'SF Pro Display', 'Inter', 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif";

export const themeConfig: ThemeConfig = {
  token: {
    colorPrimary: palette.primary,
    colorPrimaryHover: palette.primaryStrong, // 黑底主按钮 hover 提亮为深灰
    colorPrimaryActive: "#000000",
    colorInfo: palette.primary,
    colorLink: palette.link,
    colorLinkHover: palette.linkHover,
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
      siderBg: palette.dashboard.card,
      headerBg: palette.dashboard.card,
      bodyBg: palette.dashboard.bg,
      headerHeight: 56,
    },
    Menu: {
      itemBg: "transparent",
      subMenuItemBg: "transparent",
      itemSelectedBg: palette.dashboard.purpleSoft,
      itemSelectedColor: palette.dashboard.purple,
      itemColor: palette.dashboard.textSecondary,
      itemHoverBg: palette.dashboard.purpleSoft,
      itemHoverColor: palette.dashboard.text,
      itemHeight: 38,
      itemMarginInline: 8,
      itemBorderRadius: 8,
      groupTitleColor: palette.dashboard.textMuted,
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
      inkBarColor: palette.dashboard.purple,
      itemSelectedColor: palette.dashboard.purple,
      itemColor: palette.dashboard.textSecondary,
      titleFontSize: 15,
    },
  },
};
