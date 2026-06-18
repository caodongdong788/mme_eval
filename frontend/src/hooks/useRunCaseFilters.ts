import { useEffect, useMemo, useState } from "react";
import { api, CASE_LIST_LIMIT, CaseRow, ReviewStats } from "../api/index";
import { CaseFilters } from "../components/FilterToolbar";

function readSavedFilters(filtersKey: string): {
  filters: CaseFilters;
  onlyPending: boolean;
  reviewFilter?: string;
} {
  try {
    const raw = sessionStorage.getItem(filtersKey);
    if (raw) return JSON.parse(raw);
  } catch {
    /* ignore */
  }
  return { filters: {}, onlyPending: false };
}

export function useRunCaseFilters(runId: number) {
  const filtersKey = `run:${runId}:caseFilters`;
  const saved = readSavedFilters(filtersKey);

  const [cases, setCases] = useState<CaseRow[]>([]);
  const [filters, setFilters] = useState<CaseFilters>(() => saved.filters);
  const [reviewStats, setReviewStats] = useState<ReviewStats | null>(null);
  const [queueIds, setQueueIds] = useState<Set<string>>(new Set());
  const [onlyPending, setOnlyPending] = useState<boolean>(() => saved.onlyPending);
  const [reviewFilter, setReviewFilter] = useState<string | undefined>(
    () => saved.reviewFilter
  );

  useEffect(() => {
    sessionStorage.setItem(
      filtersKey,
      JSON.stringify({ filters, onlyPending, reviewFilter })
    );
  }, [filtersKey, filters, onlyPending, reviewFilter]);

  useEffect(() => {
    const params: Record<string, string | number | boolean> = {
      ...filters,
      limit: CASE_LIST_LIMIT,
    };
    if (onlyPending) params.review_pending = true;
    api.listCaseResults(runId, params).then(setCases);
    api.getReviewStats(runId).then(setReviewStats).catch(() => setReviewStats(null));
    api
      .getReviewQueue(runId, filters)
      .then((q) => setQueueIds(new Set(q.map((it) => it.sample_id))))
      .catch(() => setQueueIds(new Set()));
  }, [runId, filters, onlyPending]);

  const shownCases = useMemo(() => {
    let result = cases;
    if (reviewFilter === "agree" || reviewFilter === "override") {
      result = result.filter((c) => c.review?.verdict === reviewFilter);
    } else if (reviewFilter === "none") {
      result = result.filter((c) => !c.review);
    }
    return result;
  }, [cases, reviewFilter]);

  const hasActiveFilters =
    onlyPending ||
    reviewFilter != null ||
    ["release_passed", "level", "turns", "stability", "guideline"].some(
      (k) => filters[k] != null
    );

  const resetFilters = () => {
    setFilters({});
    setReviewFilter(undefined);
    setOnlyPending(false);
  };

  return {
    cases,
    shownCases,
    filters,
    setFilters,
    reviewStats,
    queueIds,
    onlyPending,
    setOnlyPending,
    reviewFilter,
    setReviewFilter,
    hasActiveFilters,
    resetFilters,
  };
}
