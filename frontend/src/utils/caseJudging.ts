export interface CaseVerdict {
  name: string;
  passed: boolean;
  score?: number;
  max_score?: number;
  reason?: string;
  failure_tags?: string[];
  evidence?: string[];
  details?: {
    satisfied_points?: string[];
    issue_audits?: Array<{
      type?: "partial" | "missing" | "contradicted" | "hallucination" | "other" | string;
      requirement?: string;
      reason?: string;
      evidence?: string[];
    }>;
    [key: string]: unknown;
  };
}
