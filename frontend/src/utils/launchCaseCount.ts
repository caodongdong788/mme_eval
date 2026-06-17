/** 与 server/services/eval_launch.py 用例筛选顺序一致：level → limit。 */
export function computeLaunchCaseCount(
  cases: readonly { level: string }[],
  levels: readonly string[],
  limit: number
): number {
  let filtered = cases;
  if (levels.length > 0) {
    const levelSet = new Set(levels);
    filtered = cases.filter((c) => levelSet.has(c.level));
  }
  const total = filtered.length;
  if (limit > 0) {
    return Math.min(total, limit);
  }
  return total;
}

export function countCasesByLevel(cases: readonly { level: string }[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const c of cases) {
    if (!c.level) continue;
    counts[c.level] = (counts[c.level] ?? 0) + 1;
  }
  return counts;
}
