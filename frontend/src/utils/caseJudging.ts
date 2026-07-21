export interface CaseVerdict {
  name: string;
  passed: boolean;
  score?: number;
  max_score?: number;
  reason?: string;
  failure_tags?: string[];
  evidence?: string[];
}
