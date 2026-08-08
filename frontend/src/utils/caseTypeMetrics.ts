import type { RunDetail } from "../api";

export type CaseTypeOutcomeDatum = {
  name: string;
  total: number;
  passed: number;
  failed: number;
  ratePct: number;
};

export function buildCaseTypeOutcomeData(
  summary: RunDetail["by_case_type"] | null | undefined
): CaseTypeOutcomeDatum[] {
  return Object.entries(summary || {})
    .map(([name, bucket]) => {
      const total = Math.max(0, Number(bucket.total || 0));
      const passed = Math.min(total, Math.max(0, Number(bucket.passed || 0)));
      const failed = Math.max(0, total - passed);
      return {
        name: name || "未分类",
        total,
        passed,
        failed,
        ratePct: total ? Number(((passed / total) * 100).toFixed(1)) : 0,
      };
    })
    .sort((a, b) => b.total - a.total || a.name.localeCompare(b.name, "zh-CN"));
}
