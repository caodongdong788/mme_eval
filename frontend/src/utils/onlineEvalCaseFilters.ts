export const ONLINE_EVAL_GATE_FILTERS = [
  { text: "通过", value: "pass" },
  { text: "失败", value: "fail" },
  { text: "需人审", value: "need_human_review" },
];

export const ONLINE_EVAL_SCORE_FILTERS = [
  { text: "≥ 9.0", value: "gte9" },
  { text: "8.0 - 8.9", value: "8to9" },
  { text: "7.0 - 7.9", value: "7to8" },
  { text: "6.0 - 6.9", value: "6to7" },
  { text: "< 6.0", value: "lt6" },
];

export const ONLINE_EVAL_GRADE_FILTERS = [
  { text: "优秀", value: "excellent" },
  { text: "可上线优质", value: "high_quality" },
  { text: "可接受", value: "acceptable" },
  { text: "风险样本", value: "risky" },
  { text: "不合格", value: "fail" },
];

interface OnlineEvalCaseFilterTarget {
  gate_status?: string;
  total_score_10?: number | null;
  grade?: string;
}

export interface OnlineEvalCaseExportFilters {
  gate_status?: string[];
  score_bucket?: string[];
  grade?: string[];
}

export function matchesOnlineEvalGateFilter(value: unknown, row: OnlineEvalCaseFilterTarget): boolean {
  return row.gate_status === String(value);
}

export function matchesOnlineEvalGradeFilter(value: unknown, row: OnlineEvalCaseFilterTarget): boolean {
  return row.grade === String(value);
}

export function matchesOnlineEvalScoreFilter(value: unknown, row: OnlineEvalCaseFilterTarget): boolean {
  const score = row.total_score_10;
  if (typeof score !== "number" || !Number.isFinite(score)) return false;

  switch (String(value)) {
    case "gte9":
      return score >= 9;
    case "8to9":
      return score >= 8 && score < 9;
    case "7to8":
      return score >= 7 && score < 8;
    case "6to7":
      return score >= 6 && score < 7;
    case "lt6":
      return score < 6;
    default:
      return false;
  }
}

export function filterOnlineEvalCasesBySelection<T extends OnlineEvalCaseFilterTarget>(
  cases: T[],
  filters: OnlineEvalCaseExportFilters
): T[] {
  const gateValues = filters.gate_status ?? [];
  const scoreBuckets = filters.score_bucket ?? [];
  const gradeValues = filters.grade ?? [];
  return cases.filter(
    (row) =>
      (gateValues.length === 0 || gateValues.includes(row.gate_status ?? "")) &&
      (scoreBuckets.length === 0 ||
        scoreBuckets.some((bucket) => matchesOnlineEvalScoreFilter(bucket, row))) &&
      (gradeValues.length === 0 || gradeValues.includes(row.grade ?? ""))
  );
}
