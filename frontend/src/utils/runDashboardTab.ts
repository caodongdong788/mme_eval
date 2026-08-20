export const RUN_DASHBOARD_TABS = [
  "overview",
  "detail",
  "attribution",
  "diff",
] as const;

export type RunDashboardTab = (typeof RUN_DASHBOARD_TABS)[number];

export function isRunDashboardTab(value: string | null | undefined): value is RunDashboardTab {
  return RUN_DASHBOARD_TABS.includes(value as RunDashboardTab);
}

/** 从地址恢复当前看板页签；无效值安全回退到默认页。 */
export function runDashboardTabFromSearch(search: string): RunDashboardTab | null {
  const tab = new URLSearchParams(search).get("tab");
  return isRunDashboardTab(tab) ? tab : null;
}

/** 保留其它查询参数，只更新看板页签。 */
export function withRunDashboardTab(search: string, tab: RunDashboardTab): string {
  const params = new URLSearchParams(search);
  params.set("tab", tab);
  return `?${params.toString()}`;
}
