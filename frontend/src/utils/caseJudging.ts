export interface CaseVerdict {
  name: string;
  passed: boolean;
  score?: number;
  max_score?: number;
  reason?: string;
  failure_tags?: string[];
  adjudicated?: boolean;
  evidence?: string[];
}

export function scoringPointWeight(v: CaseVerdict): number | null {
  const ev: string = (v.evidence && v.evidence[0]) || "";
  const m = /\[[^\]]*?([+-]\d+)\]/.exec(ev);
  return m ? Number(m[1]) : null;
}

export function guidelineMatch(
  detail: { case?: { scoring_points?: Array<{ guideline?: string }> } },
  scoringPoints: CaseVerdict[]
): { rate: number; matched: number; total: number } | null {
  const pts = detail?.case?.scoring_points || [];
  const anchored = pts.map((sp, i) => (sp?.guideline ? i : -1)).filter((i) => i >= 0);
  if (anchored.length === 0) return null;
  const passedByIdx: Record<number, boolean> = {};
  scoringPoints.forEach((v) => {
    const m = /point(\d+)$/.exec(v?.name || "");
    if (m) passedByIdx[Number(m[1])] = !!v.passed;
  });
  const matched = anchored.filter((i) => passedByIdx[i]).length;
  return { rate: matched / anchored.length, matched, total: anchored.length };
}
