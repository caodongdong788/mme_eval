import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  type PairwiseConfidenceKind,
  type PairwiseCaseVerdict,
  type PairwiseDetail,
} from "../api/index";
import { formatApiError } from "../utils/apiError";
import { usePollingTask } from "./usePollingTask";

export type PairwiseRagFilter = "triggered" | "not_triggered" | "unknown";

const RAG_TRIGGERED_STATUSES = new Set(["hit", "miss", "failed", "triggered"]);

export function pairwiseRagFilterValue(
  verdict: Pick<PairwiseCaseVerdict, "rag_status_a" | "rag_status_b">
): PairwiseRagFilter {
  const statuses = [verdict.rag_status_a, verdict.rag_status_b];
  if (statuses.some((status) => RAG_TRIGGERED_STATUSES.has(status))) return "triggered";
  if (statuses.every((status) => status === "not_triggered")) return "not_triggered";
  return "unknown";
}

export function usePairwiseDetail(comparisonId: number) {
  const [detail, setDetail] = useState<PairwiseDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [conclusionFilter, setConclusionFilter] = useState<"A" | "B" | "tie" | undefined>();
  const [ragFilter, setRagFilter] = useState<PairwiseRagFilter | undefined>();
  const [confidenceFilter, setConfidenceFilter] = useState<
    PairwiseConfidenceKind | undefined
  >();
  const [tablePage, setTablePage] = useState(1);
  const didMountFiltersRef = useRef(false);

  const load = useCallback(async () => {
    if (!comparisonId) return;
    try {
      const next = await api.getPairwise(comparisonId);
      setDetail(next);
      setDetailError(null);
    } catch (error) {
      setDetailError(formatApiError(error, "加载对比详情失败"));
    }
  }, [comparisonId]);

  useEffect(() => {
    load();
  }, [load]);

  usePollingTask(load, [load], {
    enabled: detail?.status === "running",
    intervalMs: 2500,
  });

  useEffect(() => {
    if (!didMountFiltersRef.current) {
      didMountFiltersRef.current = true;
      return;
    }
    setTablePage(1);
  }, [conclusionFilter, ragFilter, confidenceFilter]);

  const filtered = useMemo(() => {
    const matchesConclusion = (v: PairwiseCaseVerdict) =>
      !conclusionFilter || v.winner === conclusionFilter;
    const matchesRag = (v: PairwiseCaseVerdict) =>
      !ragFilter || pairwiseRagFilterValue(v) === ragFilter;
    const matchesConfidence = (v: PairwiseCaseVerdict) =>
      !confidenceFilter || v.confidence_kind === confidenceFilter;
    return (detail?.verdicts || []).filter(
      (v) => matchesConclusion(v) && matchesRag(v) && matchesConfidence(v)
    );
  }, [detail?.verdicts, conclusionFilter, ragFilter, confidenceFilter]);

  const hasActiveFilters = Boolean(conclusionFilter || ragFilter || confidenceFilter);

  const resetFilters = () => {
    setConclusionFilter(undefined);
    setRagFilter(undefined);
    setConfidenceFilter(undefined);
  };

  const summary = detail?.summary || {};
  const total = summary.total ?? 0;
  const aWins = summary.a_wins ?? 0;
  const bWins = summary.b_wins ?? 0;
  const ties = summary.ties ?? 0;
  const byDim = summary.by_dimension || {};
  const diffKeys = Object.keys(detail?.subject_diff || {});
  const totalCases = detail?.total_cases || 0;
  const doneCases = detail?.done_cases || 0;
  const pct = totalCases ? Math.round((doneCases / totalCases) * 100) : 0;
  const orderSensitiveN = summary.order_sensitive_count ?? 0;
  const safetyDoubtN = summary.safety_doubt_count ?? 0;
  const humanCalibratedN = summary.human_calibrated_count ?? 0;
  const runAName = detail?.run_a_name || `运行 #${detail?.run_a_id}`;
  const runBName = detail?.run_b_name || `运行 #${detail?.run_b_id}`;
  const overall = summary.overall_winner;
  const conclusion =
    overall === "B"
      ? `${runBName} 整体更优`
      : overall === "A"
        ? `${runAName} 整体更优（本次相对回退）`
        : "两次评测整体持平";

  return {
    detail,
    detailError,
    conclusionFilter,
    setConclusionFilter,
    ragFilter,
    setRagFilter,
    confidenceFilter,
    setConfidenceFilter,
    tablePage,
    setTablePage,
    filtered,
    hasActiveFilters,
    resetFilters,
    load,
    summary,
    total,
    aWins,
    bWins,
    ties,
    byDim,
    diffKeys,
    totalCases,
    doneCases,
    pct,
    orderSensitiveN,
    safetyDoubtN,
    humanCalibratedN,
    runAName,
    runBName,
    conclusion,
  };
}
