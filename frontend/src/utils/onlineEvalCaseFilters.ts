export const ONLINE_EVAL_GATE_FILTERS = [
  { text: "通过", value: "pass" },
  { text: "失败", value: "fail" },
  { text: "需人审", value: "need_human_review" },
];

export const ONLINE_EVAL_SCORE_FILTERS = [
  { text: "≥ 40.5", value: "gte40_5" },
  { text: "36 - 40.4", value: "36to40_5" },
  { text: "27 - 35.9", value: "27to36" },
  { text: "< 27", value: "lt27" },
];

export const ONLINE_EVAL_ROLE_SCORE_FILTERS = [
  { text: "≥ 13.5", value: "gte13_5" },
  { text: "12 - 13.4", value: "12to13_5" },
  { text: "9 - 11.9", value: "9to12" },
  { text: "< 9", value: "lt9" },
];

export const ONLINE_EVAL_GRADE_FILTERS = [
  { text: "优秀", value: "excellent" },
  { text: "良好", value: "good" },
  { text: "合格", value: "qualified" },
  { text: "不合格", value: "unqualified" },
];

interface OnlineEvalCaseFilterTarget {
  gate_status?: string;
  total_score?: number | null;
  grade?: string;
  score_breakdown?: Record<string, number | undefined> | null;
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
  const score = row.total_score;
  if (typeof score !== "number" || !Number.isFinite(score)) return false;

  switch (String(value)) {
    case "gte40_5":
      return score >= 40.5;
    case "36to40_5":
      return score >= 36 && score < 40.5;
    case "27to36":
      return score >= 27 && score < 36;
    case "lt27":
      return score < 27;
    default:
      return false;
  }
}

function matchesRoleScoreBucket(score: number, bucket: string): boolean {
  switch (bucket) {
    case "gte13_5":
      return score >= 13.5;
    case "12to13_5":
      return score >= 12 && score < 13.5;
    case "9to12":
      return score >= 9 && score < 12;
    case "lt9":
      return score < 9;
    default:
      return false;
  }
}

export function matchesOnlineEvalRoleScoreFilter(
  value: unknown,
  row: OnlineEvalCaseFilterTarget,
  key: "doctor_score" | "nurse_score" | "patient_score"
): boolean {
  const score = row.score_breakdown?.[key];
  if (typeof score !== "number" || !Number.isFinite(score)) return false;
  return matchesRoleScoreBucket(score, String(value));
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
