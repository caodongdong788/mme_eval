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
  default_evaluation_mode: "single_turn" | "multi_turn";
  suite_type: "capability" | "regression";
  created_by?: string | null;
  created_at?: string | null;
}

export interface BenchmarkCoverage {
  total: number;
  by_level: Record<string, number>;
  by_scenario: Record<string, number>;
  by_source: Record<string, number>;
  by_case_type: Record<string, number>;
  dimensions: Record<string, number>;
  assertion_types: Record<string, number>;
  mechanisms: Record<string, number>;
  coverage_rate: Record<string, number>;
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
  judge_error?: boolean;
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

export interface BenchmarkCaseContent {
  benchmark_id: number;
  sample_id: string;
  case_file: string;
  case: Record<string, any>;
}

export interface RunSummary {
  id: number;
  run_slug: string;
  name: string;
  status: string;
  trigger_type: "manual" | "scheduled" | "open_api";
  benchmark_id?: number | null;
  scheduled_evaluation_id?: number | null;
  adapter_type: string;
  total: number;
  passed: number;
  pass_rate: number;
  medical_safety_failed: number;
  n_runs: number;
  started_at?: string | null;
  finished_at?: string | null;
  created_at?: string | null;
  created_by?: string | null;
  error_msg: string;
  has_traces: boolean;
  pinned: boolean;
  parent_run_id?: number | null;
  evaluation_mode: "single_turn" | "multi_turn";
}

export interface ScheduledEvaluation {
  id: number;
  name: string;
  benchmark_id: number;
  enabled: boolean;
  schedule_kind: "daily" | "weekly";
  schedule_time: string;
  weekdays: number[];
  evaluation_mode: "single_turn" | "multi_turn";
  levels: string[];
  limit: number;
  repeat: number;
  enable_rag: boolean;
  enable_judge: boolean;
  judge_model_id?: number | null;
  user_simulator_model_id?: number | null;
  next_run_at?: string | null;
  last_run_at?: string | null;
  last_error: string;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
}

export type ScheduledEvaluationPayload = Omit<
  ScheduledEvaluation,
  "id" | "next_run_at" | "last_run_at" | "last_error" | "created_at" | "updated_at" | "created_by"
>;

export interface RunDetail extends RunSummary {
  description: string;
  judge_overrides: Record<string, any>;
  adapter_overrides: Record<string, any>;
  grading: Record<string, any>;
  stability_distribution: Record<string, number>;
  latency_summary: Record<string, any>;
  ttft_summary: Record<string, any>;
  token_summary: Record<string, any>;
  pass_rate_ci: Record<string, any>;
  guideline_match: Record<string, any>;
  failure_tag_counter: Record<string, number>;
  judge_fingerprints: Record<string, string>;
  by_level: Record<string, { total: number; passed: number; medical_safety_failed?: number }>;
  by_scenario: Record<string, { total: number; passed: number }>;
  by_case_type: Record<string, { total: number; passed: number }>;
  config_snapshot: Record<string, any>;
}

export interface CaseRow {
  id: number;
  sample_id: string;
  scenario: string;
  case_type: string;
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
  ttft_ms?: number | null;
  total_tokens?: number | null;
  cost?: number | null;
  n_turns?: number;
  /** 真实 Langfuse 工具链中的医学文献 RAG 调用状态，而不是 Run 的 enable_rag 开关。 */
  rag_status?: "hit" | "miss" | "failed" | "triggered" | "not_triggered" | "unknown";
  failure_tags: string[];
  review?: ReviewSummary | null;
  langfuse_trace_url?: string | null;
}

export interface GuidelineScore {
  id: string;
  dimension: string;
  criterion: string[];
  reference_answers?: string[];
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

export interface AttributionRecommendation {
  priority: "P0" | "P1" | "P2" | string;
  target: string;
  action: string;
  expected_effect?: string;
  verification: string;
}

export interface AttributionCause {
  code: string;
  label: string;
  owner: string;
  confidence: number;
  reason?: string;
  evidence_refs?: string[];
}

export interface AttributionDeductionAnalysis {
  deduction_id: string;
  dimension: string;
  deduction_validation: "supported" | "questionable" | "insufficient_evidence" | string;
  issue_type: string;
  required_information: string[];
  finding: string;
  causal_chain: Array<{
    stage: string;
    status: "pass" | "fail" | "unknown" | "not_applicable" | string;
    finding: string;
    evidence_refs?: string[];
  }>;
  primary_cause: AttributionCause;
  contributing_causes: AttributionCause[];
  rag_diagnosis: {
    needed: boolean;
    called: boolean;
    query_quality: string;
    relevant_information_stage: string;
    answer_usage: string;
    finding: string;
  };
  recommendations: AttributionRecommendation[];
}

export interface CaseAttributionAnalysis {
  analysis_status: "complete" | "partial" | "insufficient_evidence" | string;
  overall: {
    primary_cause_code: string;
    primary_cause_label: string;
    owner: string;
    confidence: number;
    summary: string;
    affected_deduction_ids: string[];
  };
  rag_overview: {
    needed: boolean;
    needed_reason?: string;
    enabled: boolean;
    actually_called: boolean;
    call_count: number;
    diagnosis: string;
    summary: string;
  };
  deduction_analyses: AttributionDeductionAnalysis[];
  global_recommendations: AttributionRecommendation[];
  limitations: string[];
}

export interface CaseAttribution {
  available: boolean;
  stale: boolean;
  analysis?: CaseAttributionAnalysis | null;
  metadata: {
    prompt_version?: string;
    model?: string;
    provider?: string;
    generated_at?: string;
    input_hash?: string;
  };
}

export interface AttributionTaskItem {
  sample_id: string;
  scenario: string;
  case_type: string;
  status: "pending" | "running" | "success" | "failed" | string;
  error_msg: string;
  attribution_available: boolean;
  attribution_stale: boolean;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface AttributionTask {
  id: number;
  run_id: number;
  judge_model_id: number;
  judge_model_name: string;
  status: "queued" | "running" | "success" | "partial" | "failed" | string;
  requested_count: number;
  total_count: number;
  skipped_count: number;
  completed_count: number;
  success_count: number;
  failed_count: number;
  running_count: number;
  pending_count: number;
  error_msg: string;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  items: AttributionTaskItem[];
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
    /** 按用例聚合的进度，用于批量重新评测。 */
    case_done?: number;
    case_total?: number;
    percent?: number;
    /** 后端已持久化本次重试的最终进度。 */
    completed?: boolean;
    phases?: Record<string, { label: string; total: number; done: number }>;
    context?: {
      kind?: string;
      sample_id?: string;
      sample_ids?: string[];
    };
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
    enable_rag?: boolean;
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

export interface EvaluationAccount {
  pool: "stateless" | "stateful";
  pool_label: string;
  phone: string;
  verification_code: string;
  user_id: string;
  usage: string;
}

export interface EvaluationAccountsConfig {
  accounts: EvaluationAccount[];
  allocation_rule: string;
}

export type OpenApiPermission =
  | "benchmarks:read"
  | "judge_models:read"
  | "evaluations:create"
  | "evaluations:read";

export interface OpenApiAccessKey {
  id: number;
  name: string;
  api_key: string;
  key_prefix: string;
  permissions: OpenApiPermission[];
  created_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  last_used_at?: string | null;
}

export interface EvaluationStandard {
  roles: Array<{
    key: "doctor" | "nurse" | "user";
    label: string;
    max_score: number;
    raw_max_score: number;
    dimension_count: number;
    normalized: boolean;
  }>;
  dimensions: Array<{
    key: string;
    label: string;
    role: "doctor" | "nurse" | "user";
    description: string;
    zero_score_description: string;
    full_score_description: string;
    max_score: number;
    binary: boolean;
    score_range: string;
  }>;
  score_anchors: Array<{ score: number; description: string }>;
  end_max_scores: Record<"doctor" | "nurse" | "user", number>;
  total_max_score: number;
  grades: Array<{ grade: string; min_score: number; passed: boolean }>;
  medical_safety_zeroes_total: boolean;
  guideline_rule: string;
  guideline_rule_description: string;
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
  latency_summary?: Record<string, number>;
  ttft_summary?: Record<string, number>;
  token_summary?: Record<string, number | string>;
  reliability?: Record<string, number>;
  by_case_type?: Record<string, { total: number; passed: number }>;
}

export interface PairwiseComparability {
  comparable: boolean;
  reasons: string[];
  subject_diff: Record<string, { a: any; b: any }>;
  rag_analysis: PairwiseRagAnalysis;
}

export interface PairwiseRagAnalysis {
  rag_side: "A" | "B" | null;
  common_cases: number;
  selected_cases: number;
  excluded_cases: number;
  unknown_cases: number;
  baseline_triggered_cases: number;
  a_status_counts: Record<string, number>;
  b_status_counts: Record<string, number>;
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
  rag_scope?: {
    rag_side: "A" | "B";
    common_cases: number;
    selected_cases: number;
    excluded_cases: number;
    unknown_cases: number;
    rag_status_counts: Record<string, number>;
  };
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
  rag_status_a: "hit" | "miss" | "failed" | "triggered" | "not_triggered" | "unknown";
  rag_status_b: "hit" | "miss" | "failed" | "triggered" | "not_triggered" | "unknown";
  winner: "A" | "B" | "tie";
  confidence_kind: PairwiseConfidenceKind;
  human_calibrated: boolean;
  swap_consistent: boolean;
  dimension_winners: Record<string, string>;
  reason: string;
  order_runs?: {
    top: "A" | "B";
    winner: "A" | "B" | "tie";
    /** 单次换序的八维结果；旧对比没有该留痕。 */
    dimension_winners?: Record<string, "A" | "B" | "tie">;
    reason: string;
  }[];
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

export interface PairwiseRunObservability {
  latency_summary: Record<string, number>;
  ttft_summary: Record<string, number>;
  token_summary: Record<string, number | string>;
}

export interface PairwiseDetail extends PairwiseComparison {
  verdicts: PairwiseCaseVerdict[];
  run_a_observability: PairwiseRunObservability;
  run_b_observability: PairwiseRunObservability;
}

export interface PairwiseCreatePayload {
  run_a_id: number;
  run_b_id: number;
  judge_model_id: number;
  scope?: "all" | "divergent_only" | "rag_triggered_only";
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
