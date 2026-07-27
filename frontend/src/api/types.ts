export interface MeResponse {
  auth_required: boolean;
  user: { open_id: string; name: string; avatar_url: string } | null;
}

export interface Benchmark {
  id: number;
  name: string;
  description: string;
  version: string;
  source: string;
  case_count: number;
  tags: string[];
  levels: string[];
  created_by?: string | null;
  created_at?: string | null;
}

export interface RejudgePayload {
  judge?: {
    provider?: string;
    model?: string;
    base_url?: string;
    api_version?: string;
    api_key_env?: string;
    api_key?: string;
    temperature?: number;
  };
  judge_model_id?: number;
  cases_benchmark_id?: number;
  only_release_failed?: boolean;
}

export interface DeriveBenchmarkYamlPayload {
  name: string;
  description?: string;
  yaml_text: string;
}

export interface OverwriteBenchmarkYamlPayload {
  yaml_text: string;
}

export interface CasesYaml {
  benchmark_id: number;
  count: number;
  yaml_text: string;
}

export interface CaseLogicOverride {
  sample_id: string;
  evaluation?: Record<string, any> | null;
}

export interface PreviewRejudgePayload {
  case_override?: CaseLogicOverride | null;
  yaml_text?: string;
}

export interface CaseScores {
  medical_safety_passed: boolean;
  release_passed: boolean;
  composite_score?: number | null;
  grade: string;
  dimension_raw_scores: Record<string, number | null>;
  dimension_scores: Record<string, number | null>;
  dimension_max: Record<string, number>;
  end_scores: Record<string, number>;
  guideline_scores: GuidelineScore[];
  score_deductions: string[];
  failure_tags: string[];
  verdicts: Array<{
    name?: string;
    passed?: boolean | null;
    score?: number | null;
    max_score?: number | null;
    reason?: string | null;
  }>;
}

export interface PreviewRejudgeResult {
  sample_id: string;
  current: CaseScores;
  preview: CaseScores;
  changed: boolean;
  case_result: Record<string, any>;
}

export interface CaseBrief {
  sample_id: string;
  scenario: string;
  case_type: string;
  is_bug: string;
  level: string;
}

export interface BenchmarkCaseYaml {
  benchmark_id: number;
  sample_id: string;
  case_file: string;
  yaml_text: string;
}

export interface RunSummary {
  id: number;
  run_slug: string;
  name: string;
  status: string;
  benchmark_id?: number | null;
  adapter_type: string;
  total: number;
  passed: number;
  pass_rate: number;
  medical_safety_failed: number;
  n_runs: number;
  started_at?: string | null;
  finished_at?: string | null;
  created_at?: string | null;
  error_msg: string;
  has_traces: boolean;
  pinned: boolean;
  parent_run_id?: number | null;
  evaluation_mode: "single_turn" | "multi_turn";
}

export interface RunDetail extends RunSummary {
  description: string;
  judge_overrides: Record<string, any>;
  adapter_overrides: Record<string, any>;
  grading: Record<string, any>;
  stability_distribution: Record<string, number>;
  latency_summary: Record<string, any>;
  token_summary: Record<string, any>;
  pass_rate_ci: Record<string, any>;
  guideline_match: Record<string, any>;
  failure_tag_counter: Record<string, number>;
  judge_fingerprints: Record<string, string>;
  by_level: Record<string, { total: number; passed: number; medical_safety_failed?: number }>;
  by_scenario: Record<string, { total: number; passed: number }>;
  config_snapshot: Record<string, any>;
}

export interface CaseRow {
  id: number;
  sample_id: string;
  scenario: string;
  sub_scenario: string;
  level: string;
  medical_safety_passed: boolean;
  release_passed: boolean;
  composite_score?: number | null;
  grade: string;
  stability: string;
  guideline_earned?: number | null;
  guideline_max?: number | null;
  latency_ms?: number | null;
  total_tokens?: number | null;
  cost?: number | null;
  n_turns?: number;
  failure_tags: string[];
  review?: ReviewSummary | null;
  langfuse_trace_url?: string | null;
}

export interface GuidelineScore {
  id: string;
  dimension: string;
  criterion: string[];
  checkpoints?: string[];
  deduction_rule?: string;
  trigger?: string;
  applicable?: boolean;
  score: number;
  max_score: number;
  deduction?: number;
  missed_points?: string[];
  reason: string;
  evidence: string[];
}

export interface ReviewSummary {
  verdict: "agree" | "override";
  reviewer?: string | null;
  suggestion?: string | null;
  comment?: string | null;
  count: number;
}

export interface Annotation {
  id: number;
  reviewer?: string | null;
  verdict: "agree" | "override";
  suggestion?: string | null;
  comment?: string | null;
  created_at?: string | null;
}

export interface ReviewQueueItem {
  sample_id: string;
  scenario: string;
  level: string;
  release_passed: boolean;
  composite_score?: number | null;
  failure_tags: string[];
  reasons: string[];
  reviewed: boolean;
  annotations: Annotation[];
}

export interface ReviewStats {
  queue_total: number;
  reviewed: number;
  pending: number;
  agree: number;
  override: number;
  agree_rate: number;
  disagree_rate: number;
}

export interface AnnotatePayload {
  verdict: "agree" | "override";
  suggestion?: string;
  comment?: string;
}

export interface ProgressInfo {
  status: string;
  progress?: {
    current?: string | null;
    current_label?: string;
    done?: number;
    total?: number;
    percent?: number;
    phases?: Record<string, { label: string; total: number; done: number }>;
  } | null;
}

export interface RunCreatePayload {
  benchmark_id: number;
  run_name?: string;
  evaluation_mode?: "single_turn" | "multi_turn";
  levels?: string[];
  limit?: number;
  repeat?: number;
  judge?: {
    enabled?: boolean;
    provider?: string;
    model?: string;
    base_url?: string;
    api_version?: string;
    api_key_env?: string;
    api_key?: string;
    temperature?: number;
  };
  adapter?: {
    model?: string;
    base_url?: string;
    system_prompt?: string;
    api_key?: string;
  };
  judge_model_id?: number;
  user_simulator_model_id?: number;
}

export interface JudgeDefaults {
  provider: string;
  model: string;
  base_url: string;
  api_version: string;
  model_options: string[];
}

export interface EvaluationStandard {
  dimensions: Array<{
    key: string;
    label: string;
    role: "doctor" | "nurse" | "user";
    description: string;
    max_score: number;
    binary: boolean;
  }>;
  end_max_scores: Record<"doctor" | "nurse" | "user", number>;
  total_max_score: number;
  grades: Array<{ grade: string; min_score: number }>;
  medical_safety_zeroes_total: boolean;
  guideline_rule: string;
}

export interface JudgeModel {
  id: number;
  name: string;
  provider: string;
  model: string;
  base_url: string;
  api_version: string;
  temperature?: number | null;
  enable_thinking?: boolean | null;
  pairwise_concurrency: number;
  has_api_key: boolean;
  created_by?: string | null;
  created_at?: string | null;
}

export interface JudgeModelPayload {
  name?: string;
  provider?: string;
  model?: string;
  base_url?: string;
  api_version?: string;
  temperature?: number | null;
  enable_thinking?: boolean | null;
  pairwise_concurrency?: number;
  api_key?: string;
}

export interface TrendPoint {
  run_id: number;
  run_slug: string;
  name: string;
  finished_at?: string | null;
  pass_rate: number;
  total: number;
  passed: number;
  medical_safety_failed: number;
  avg_composite?: number | null;
  avg_dimension: Record<string, number>;
  failure_tag_counter: Record<string, number>;
  stability_distribution: Record<string, number>;
  pass_rate_ci: Record<string, any>;
}

export interface PairwiseComparability {
  comparable: boolean;
  reasons: string[];
  subject_diff: Record<string, { a: any; b: any }>;
}

export interface PairwiseSummary {
  total: number;
  a_wins: number;
  b_wins: number;
  ties: number;
  low_confidence: number;
  order_sensitive_count?: number;
  safety_doubt_count?: number;
  human_calibrated_count?: number;
  b_win_rate: number;
  overall_winner: "A" | "B" | "tie";
  by_dimension: Record<string, { A: number; B: number; tie: number }>;
  regressions: string[];
  improvements: string[];
}

export interface PairwiseComparison {
  id: number;
  run_a_id: number;
  run_b_id: number;
  run_a_name?: string | null;
  run_b_name?: string | null;
  note: string;
  judge_model: string;
  judge_fingerprint: string;
  status: string;
  error_msg: string;
  scope: string;
  total_cases: number;
  done_cases: number;
  subject_diff: Record<string, { a: any; b: any }>;
  summary: Partial<PairwiseSummary>;
  created_at?: string | null;
  finished_at?: string | null;
}

export type PairwiseConfidenceKind = "high" | "order" | "safety" | "human";

export interface PairwiseCaseVerdict {
  sample_id: string;
  scenario?: string;
  sub_scenario?: string;
  winner: "A" | "B" | "tie";
  confidence_kind: PairwiseConfidenceKind;
  human_calibrated: boolean;
  swap_consistent: boolean;
  dimension_winners: Record<string, string>;
  reason: string;
  order_runs?: { top: "A" | "B"; winner: "A" | "B" | "tie"; reason: string }[];
  auto_winner?: "A" | "B" | "tie" | null;
  auto_confidence?: string | null;
  auto_dimension_winners?: Record<string, string> | null;
  auto_reason?: string | null;
  confidence?: string;
}

export interface PairwiseCalibratePayload {
  winner: "A" | "B" | "tie";
  dimension_winners: Record<string, "A" | "B" | "tie">;
  reason: string;
}

export interface PairwiseDetail extends PairwiseComparison {
  verdicts: PairwiseCaseVerdict[];
}

export interface PairwiseCreatePayload {
  run_a_id: number;
  run_b_id: number;
  judge_model_id: number;
  scope?: "all" | "divergent_only";
  note?: string;
}

export interface RunDiffSide {
  id: number;
  run_slug: string;
  pass_rate: number;
  passed: number;
  total: number;
}

export type DiffChangeKind = "regression" | "improvement" | "unchanged";

export interface DiffCaseRow {
  sample_id: string;
  scenario: string;
  sub_scenario: string;
  level: string;
  current_release_passed: boolean | null;
  baseline_release_passed: boolean | null;
  current_score: number | null;
  baseline_score: number | null;
  score_delta: number | null;
  change: DiffChangeKind;
}

export interface RunDiff {
  current: RunDiffSide;
  against: RunDiffSide;
  pass_rate_delta: number;
  regressions: string[];
  improvements: string[];
  judge_logic_changed: boolean;
  fingerprint_changes: Record<string, { against: unknown; current: unknown }>;
  cases: DiffCaseRow[];
}
