import axios from "axios";

// 默认请求超时（毫秒）。评测/导出等长任务的端点单独放宽（见 LONG_TIMEOUT）。
const DEFAULT_TIMEOUT_MS = 30_000;
export const LONG_TIMEOUT_MS = 120_000;

const http = axios.create({
  baseURL: "/api",
  withCredentials: true,
  timeout: DEFAULT_TIMEOUT_MS,
});

export interface MeResponse {
  auth_required: boolean;
  user: { open_id: string; name: string; avatar_url: string } | null;
}

export const FEISHU_LOGIN_URL = "/api/auth/feishu/login";

// 请求拦截器：统一标注来源，便于后端/排障关联。
http.interceptors.request.use((config) => {
  config.headers = config.headers ?? {};
  config.headers["X-Requested-With"] = "mme-frontend";
  return config;
});

// 会话过期/未登录时，业务接口返回 401 → 跳登录页（避免停留在报错状态）。
http.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (
      error?.response?.status === 401 &&
      window.location.pathname !== "/login"
    ) {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// ---------------------------------------------------------------------------
// 类型（与后端 server/schemas.py 对齐）

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

// 重判可选覆盖（仅作用于本次重判，不改服务器 config.yaml）
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
  // 从判分模型库下拉选用已保存配置（连接信息 + Key 由服务端注入）
  judge_model_id?: number;
  cases_benchmark_id?: number;
  // 仅重判上线判定失败（release_passed=false）的用例；通过用例沿用源结果
  only_release_failed?: boolean;
}

// 从整段用例 YAML 改判据另存为新 benchmark（按 sample_id 只合并判据字段，未匹配丢弃）
export interface DeriveBenchmarkYamlPayload {
  name: string;
  description?: string;
  yaml_text: string;
}

// 从整段用例 YAML 改判据就地覆盖原 benchmark（合并语义同另存；内置不可覆盖）
export interface OverwriteBenchmarkYamlPayload {
  yaml_text: string;
}

export interface CasesYaml {
  benchmark_id: number;
  count: number;
  yaml_text: string;
}

// 单条用例判据覆盖（仅 4 个判据字段，sample_id 以路径为准）
export interface CaseLogicOverride {
  sample_id: string;
  expected_behavior?: Record<string, any> | null;
  hard_gates?: Record<string, any> | null;
  rubric?: Record<string, any> | null;
  scoring_points?: Record<string, any>[] | null;
}

export interface PreviewRejudgePayload {
  case_override?: CaseLogicOverride | null;
  // 等价入参：单条/多条用例 YAML，服务端按路径 sample_id 抽取判据（前端复用 YAML 编辑器内容）
  yaml_text?: string;
}

// 单用例判分快照（试判前后对比）
export interface CaseScores {
  hard_gate_passed: boolean;
  gate_passed: boolean;
  release_passed: boolean;
  composite_score?: number | null;
  grade: string;
  dimension_scores: Record<string, number | null>;
  dimension_max: Record<string, number>;
  score_profile: string;
  score_deductions: string[];
  failure_tags: string[];
  needs_human_review: boolean;
  verdicts: Array<{
    name?: string;
    passed?: boolean | null;
    score?: number | null;
    max_score?: number | null;
    reason?: string | null;
  }>;
}

// 单用例试判预览结果（纯只读旁路，不代表任何已落库变化）
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
  sub_scenario: string;
  level: string;
  score_profile: string;
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
  hard_gate_failed: number;
  n_runs: number;
  started_at?: string | null;
  finished_at?: string | null;
  created_at?: string | null;
  error_msg: string;
  has_traces: boolean;
  pinned: boolean;
  parent_run_id?: number | null;
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
  by_level: Record<string, { total: number; passed: number; hard_failed?: number }>;
  by_scenario: Record<string, { total: number; passed: number }>;
  config_snapshot: Record<string, any>;
}

export interface CaseRow {
  id: number;
  sample_id: string;
  scenario: string;
  sub_scenario: string;
  level: string;
  hard_gate_passed: boolean;
  gate_passed: boolean;
  release_passed: boolean;
  composite_score?: number | null;
  grade: string;
  score_profile: string;
  stability: string;
  needs_human_review: boolean;
  guideline_match_rate?: number | null;
  guideline_matched?: number | null;
  guideline_total?: number | null;
  latency_ms?: number | null;
  total_tokens?: number | null;
  cost?: number | null;
  n_turns?: number;
  failure_tags: string[];
  review?: ReviewSummary | null;
  langfuse_trace_url?: string | null;
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
  levels?: string[];
  // 后端 RunCreate 实际字段为 score_profiles（按评分档过滤）；原 tags 字段后端不接收，已移除以消除契约漂移。
  score_profiles?: string[];
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
}

export interface JudgeDefaults {
  provider: string;
  model: string;
  base_url: string;
  api_version: string;
  model_options: string[];
}

// 该评分档对应的用例 score_profile 映射（前端展示覆盖范围）
export interface ProfileCoverage {
  is_fallback: boolean;
  score_profile: string;
  case_count: number;
}

// 按评分档（profile）的综合分上线阈值配置（仅作用于之后发起的新评测）
export interface ReleaseThresholdItem {
  profile: string;
  label: string;
  max_total: number;
  default_threshold: number;
  override: number | null;
  effective: number;
  coverage: ProfileCoverage;
}

export interface JudgeModel {
  id: number;
  name: string;
  provider: string;
  model: string;
  base_url: string;
  api_version: string;
  temperature?: number | null;
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
  hard_gate_failed: number;
  avg_composite?: number | null;
  avg_dimension: Record<string, number>;
  failure_tag_counter: Record<string, number>;
  stability_distribution: Record<string, number>;
  pass_rate_ci: Record<string, any>;
}

// pairwise 对比（与 server/schemas.py 对齐）
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

// 两次 run 的差异（GET /runs/{id}/diff），对齐 server/compare.py::compare_runs。
export interface RunDiffSide {
  id: number;
  run_slug: string;
  pass_rate: number;
  passed: number;
  total: number;
}

export interface RunDiff {
  current: RunDiffSide;
  against: RunDiffSide;
  pass_rate_delta: number;
  regressions: string[];
  improvements: string[];
  judge_logic_changed: boolean;
  fingerprint_changes: Record<string, { against: unknown; current: unknown }>;
}

// ---------------------------------------------------------------------------
// API

// 用户可选 benchmark 口径：排除内置（内置仅作「用例模板」下载入口，不在 Benchmark 库表中列出）。
// 趋势看板 / 发起评测 / 重判判据选择等所有 benchmark 选择器统一用此函数，避免出现库里没有的项。
export const selectableBenchmarks = (list: Benchmark[]): Benchmark[] =>
  list.filter((b) => b.source !== "builtin");

export const api = {
  listBenchmarks: () => http.get<Benchmark[]>("/benchmarks").then((r) => r.data),
  getBenchmarkCases: (id: number) =>
    http.get<CaseBrief[]>(`/benchmarks/${id}/cases`).then((r) => r.data),
  uploadBenchmark: (form: FormData) =>
    http.post<Benchmark>("/benchmarks", form).then((r) => r.data),
  replaceBenchmark: (id: number, form: FormData) =>
    http.put<Benchmark>(`/benchmarks/${id}`, form).then((r) => r.data),
  updateBenchmark: (id: number, payload: { name?: string; description?: string }) =>
    http.patch<Benchmark>(`/benchmarks/${id}`, payload).then((r) => r.data),
  downloadBenchmarkUrl: (id: number) => `/api/benchmarks/${id}/download`,
  deleteBenchmark: (id: number) => http.delete(`/benchmarks/${id}`),
  deriveBenchmarkFromYaml: (id: number, payload: DeriveBenchmarkYamlPayload) =>
    http.post<Benchmark>(`/benchmarks/${id}/derive-yaml`, payload).then((r) => r.data),
  overwriteBenchmarkFromYaml: (id: number, payload: OverwriteBenchmarkYamlPayload) =>
    http.post<Benchmark>(`/benchmarks/${id}/overwrite-yaml`, payload).then((r) => r.data),

  getReleaseThresholds: () =>
    http.get<ReleaseThresholdItem[]>("/config/release-thresholds").then((r) => r.data),
  putReleaseThresholds: (overrides: Record<string, number | null>) =>
    http
      .put<ReleaseThresholdItem[]>("/config/release-thresholds", { overrides })
      .then((r) => r.data),

  listJudgeModels: () => http.get<JudgeModel[]>("/judge-models").then((r) => r.data),
  createJudgeModel: (payload: JudgeModelPayload) =>
    http.post<JudgeModel>("/judge-models", payload).then((r) => r.data),
  updateJudgeModel: (id: number, payload: JudgeModelPayload) =>
    http.patch<JudgeModel>(`/judge-models/${id}`, payload).then((r) => r.data),
  deleteJudgeModel: (id: number) => http.delete(`/judge-models/${id}`),

  listRuns: () => http.get<RunSummary[]>("/runs").then((r) => r.data),
  getRun: (id: number) => http.get<RunDetail>(`/runs/${id}`).then((r) => r.data),
  createRun: (payload: RunCreatePayload) =>
    http.post<RunSummary>("/runs", payload).then((r) => r.data),
  getProgress: (id: number) =>
    http.get<ProgressInfo>(`/runs/${id}/progress`).then((r) => r.data),
  listCaseResults: (id: number, params?: Record<string, any>) =>
    http.get<CaseRow[]>(`/runs/${id}/cases`, { params }).then((r) => r.data),
  getCaseDetail: (id: number, sampleId: string) =>
    http.get<any>(`/runs/${id}/cases/${sampleId}`).then((r) => r.data),
  getRunCasesYaml: (id: number, params?: Record<string, any>) =>
    http.get<CasesYaml>(`/runs/${id}/cases-yaml`, { params }).then((r) => r.data),
  previewRejudgeCase: (id: number, sampleId: string, payload?: PreviewRejudgePayload) =>
    http
      .post<PreviewRejudgeResult>(
        `/runs/${id}/cases/${sampleId}/preview-rejudge`,
        payload ?? {}
      )
      .then((r) => r.data),
  getReviewQueue: (id: number, params?: Record<string, any>) =>
    http.get<ReviewQueueItem[]>(`/runs/${id}/review-queue`, { params }).then((r) => r.data),
  getReviewStats: (id: number) =>
    http.get<ReviewStats>(`/runs/${id}/review-stats`).then((r) => r.data),
  getCaseAnnotations: (id: number, sampleId: string) =>
    http.get<Annotation[]>(`/runs/${id}/cases/${sampleId}/annotations`).then((r) => r.data),
  annotateCase: (id: number, sampleId: string, payload: AnnotatePayload) =>
    http.post<Annotation>(`/runs/${id}/cases/${sampleId}/annotate`, payload).then((r) => r.data),
  requestReview: (id: number, sampleId: string) =>
    http.post(`/runs/${id}/cases/${sampleId}/request-review`).then((r) => r.data),
  getFailureTagLabels: () =>
    http.get<Record<string, string>>(`/config/failure-tags`).then((r) => r.data),
  exportTranscripts: (id: number, params?: Record<string, any>) =>
    http
      .post<{ url: string; count: number; filename: string }>(
        `/runs/${id}/export-transcripts`,
        null,
        { params }
      )
      .then((r) => r.data),
  diffRun: (id: number, against: number) =>
    http.get<RunDiff>(`/runs/${id}/diff`, { params: { against } }).then((r) => r.data),

  precheckPairwise: (runAId: number, runBId: number) =>
    http
      .get<PairwiseComparability>("/compare/pairwise/precheck", {
        params: { run_a_id: runAId, run_b_id: runBId },
      })
      .then((r) => r.data),
  createPairwise: (payload: PairwiseCreatePayload) =>
    http.post<PairwiseComparison>("/compare/pairwise", payload).then((r) => r.data),
  listPairwise: (runId?: number) =>
    http
      .get<PairwiseComparison[]>("/compare/pairwise", {
        params: runId ? { run_id: runId } : undefined,
      })
      .then((r) => r.data),
  getPairwise: (id: number) =>
    http.get<PairwiseDetail>(`/compare/pairwise/${id}`).then((r) => r.data),
  updatePairwiseNote: (id: number, note: string) =>
    http.patch<PairwiseComparison>(`/compare/pairwise/${id}`, { note }).then((r) => r.data),
  deletePairwise: (id: number) =>
    http.delete(`/compare/pairwise/${id}`).then((r) => r.data),
  calibratePairwiseVerdict: (
    comparisonId: number,
    sampleId: string,
    payload: PairwiseCalibratePayload
  ) =>
    http
      .patch<PairwiseCaseVerdict>(
        `/compare/pairwise/${comparisonId}/cases/${encodeURIComponent(sampleId)}`,
        payload
      )
      .then((r) => r.data),
  resetPairwiseCalibration: (comparisonId: number, sampleId: string) =>
    http
      .delete<PairwiseCaseVerdict>(
        `/compare/pairwise/${comparisonId}/cases/${encodeURIComponent(sampleId)}`
      )
      .then((r) => r.data),

  getJudgeDefaults: () =>
    http.get<JudgeDefaults>("/config/judge-defaults").then((r) => r.data),

  getTrends: (benchmarkId: number) =>
    http
      .get<{ benchmark_id: number; points: TrendPoint[] }>("/dashboard/trends", {
        params: { benchmark_id: benchmarkId },
      })
      .then((r) => r.data),

  deleteRun: (id: number) => http.delete(`/runs/${id}`).then((r) => r.data),
  rejudgeRun: (id: number, payload?: RejudgePayload) =>
    http.post<RunSummary>(`/runs/${id}/rejudge`, payload ?? null).then((r) => r.data),
  resumeRun: (id: number) =>
    http.post<RunSummary>(`/runs/${id}/resume`).then((r) => r.data),
  renameRun: (id: number, name: string) =>
    http.patch<RunSummary>(`/runs/${id}`, { name }).then((r) => r.data),
  setPin: (id: number, pinned: boolean) =>
    http
      .post<{ id: number; pinned: boolean }>(`/runs/${id}/pin`, null, {
        params: { pinned },
      })
      .then((r) => r.data),

  getMe: () => http.get<MeResponse>("/auth/me").then((r) => r.data),
  logout: () => http.post("/auth/logout").then((r) => r.data),
};
