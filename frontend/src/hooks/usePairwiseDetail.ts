import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  api,
  type PairwiseCaseVerdict,
  type PairwiseConfidenceKind,
  type PairwiseDetail,
} from "../api/index";
import { formatApiError } from "../utils/apiError";

export function usePairwiseDetail(comparisonId: number) {
  const location = useLocation();
  const [detail, setDetail] = useState<PairwiseDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [conclusionFilter, setConclusionFilter] = useState<"A" | "B" | "tie" | undefined>();
  const [confidenceFilter, setConfidenceFilter] = useState<
    PairwiseConfidenceKind | undefined
  >();
  const [calibrateVerdict, setCalibrateVerdict] = useState<PairwiseCaseVerdict | null>(null);
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);
  const [tablePage, setTablePage] = useState(1);
  const restoredRef = useRef(false);
  const didMountFiltersRef = useRef(false);

  const load = useCallback(() => {
    if (!comparisonId) return;
    api
      .getPairwise(comparisonId)
      .then((d) => {
        setDetail(d);
        setDetailError(null);
      })
      .catch((e) => setDetailError(formatApiError(e, "加载对比详情失败")));
  }, [comparisonId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (detail?.status === "running") {
      const t = setInterval(load, 2500);
      return () => clearInterval(t);
    }
  }, [detail?.status, load]);

  useEffect(() => {
    if (restoredRef.current || !detail) return;
    const key = (location.state as { expandedKey?: string } | null)?.expandedKey;
    if (!key) return;
    const idx = (detail.verdicts || []).findIndex((v) => v.sample_id === key);
    if (idx >= 0) {
      setExpandedKeys([key]);
      setTablePage(Math.floor(idx / 20) + 1);
      requestAnimationFrame(() => {
        document
          .querySelector(`[data-row-key="${CSS.escape(key)}"]`)
          ?.scrollIntoView({ block: "center", behavior: "smooth" });
      });
    }
    restoredRef.current = true;
  }, [detail, location.state]);

  useEffect(() => {
    if (!didMountFiltersRef.current) {
      didMountFiltersRef.current = true;
      return;
    }
    setTablePage(1);
  }, [conclusionFilter, confidenceFilter]);

  const filtered = useMemo(() => {
    const matchesConclusion = (v: PairwiseCaseVerdict) =>
      !conclusionFilter || v.winner === conclusionFilter;
    const matchesConfidence = (v: PairwiseCaseVerdict) =>
      !confidenceFilter || v.confidence_kind === confidenceFilter;
    return (detail?.verdicts || []).filter(
      (v) => matchesConclusion(v) && matchesConfidence(v)
    );
  }, [detail?.verdicts, conclusionFilter, confidenceFilter]);

  const hasActiveFilters = Boolean(conclusionFilter || confidenceFilter);

  const resetFilters = () => {
    setConclusionFilter(undefined);
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
    confidenceFilter,
    setConfidenceFilter,
    calibrateVerdict,
    setCalibrateVerdict,
    expandedKeys,
    setExpandedKeys,
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
