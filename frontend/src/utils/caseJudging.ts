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

const JUDGE_PREFIX: Record<string, string> = {
  hard_gate: "硬门槛",
  rule: "规则",
  llm: "体验",
  scoring_point: "得分点",
  semantic_adjudicator: "语义裁决",
};

const JUDGE_SUFFIX: Record<string, string> = {
  red_flag: "红旗分诊",
  no_prescription: "处方边界",
  disclaimer: "免责声明",
  must_have: "必含要点",
  must_not_have: "禁含要点",
  empathy: "共情",
  clarity: "清晰度",
  actionability: "可执行性",
  safety: "安全",
  professionalism: "专业度",
  boundary: "边界感",
  factual_accuracy: "事实准确性",
  completeness: "完整性",
  relevance: "相关性",
  tone: "语气",
};

export function judgeLabel(name?: string): string {
  if (!name) return "-";
  const idx = name.indexOf(".");
  if (idx < 0) return JUDGE_PREFIX[name] || name;
  const prefix = name.slice(0, idx);
  const suffix = name.slice(idx + 1);
  const pl = JUDGE_PREFIX[prefix];
  const sl = JUDGE_SUFFIX[suffix];
  if (pl && sl) return `${pl}·${sl}`;
  if (pl) return `${pl}·${suffix}`;
  return name;
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
