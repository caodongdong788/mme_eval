// run 运行状态的单一信任源（圆点变体 + 文案）；RunsPage 与 RunDashboardPage 共用，禁止各页重复定义。
// 设计：状态用 6px 圆点 + 深灰文字（去面状彩色 Tag），文字始终保留以兼顾色觉无障碍。
export const RUN_STATUS_META: Record<string, { dot: string; text: string }> = {
  pending: { dot: "muted", text: "等待中" },
  running: { dot: "running", text: "运行中" },
  success: { dot: "pass", text: "成功" },
  failed: { dot: "fail", text: "失败" },
};

export function runStatusMeta(status: string): { dot: string; text: string } {
  return RUN_STATUS_META[status] || { dot: "muted", text: status };
}

export function RunStatusTag({ status }: { status: string; bordered?: boolean }) {
  const t = runStatusMeta(status);
  return <span className={`status-dot status-dot--${t.dot}`}>{t.text}</span>;
}
