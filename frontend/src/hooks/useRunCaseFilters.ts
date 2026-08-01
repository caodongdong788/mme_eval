import { useEffect, useMemo, useState } from "react";
import { api, CASE_LIST_LIMIT, CaseRow, ReviewStats } from "../api/index";
import {
  type CaseFilterCondition,
  buildCaseFilterValueOptions,
  filterCaseRows,
  isActiveCaseFilter,
} from "../utils/caseFilters";

function readSavedFilters(filtersKey: string): {
  conditions: CaseFilterCondition[];
} {
  try {
    const raw = sessionStorage.getItem(filtersKey);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed.conditions)) return { conditions: parsed.conditions };
    }
  } catch {
    /* ignore */
  }
  return { conditions: [] };
}

export function useRunCaseFilters(
  runId: number,
  failureTagLabel: (tag: string) => string,
  enabled = true,
) {
  const filtersKey = `run:${runId}:caseFilters`;
  const saved = readSavedFilters(filtersKey);

  const [cases, setCases] = useState<CaseRow[]>([]);
  const [filterConditions, setFilterConditions] = useState<CaseFilterCondition[]>(
    () => saved.conditions
  );
  const [reviewStats, setReviewStats] = useState<ReviewStats | null>(null);
  const [queueIds, setQueueIds] = useState<Set<string>>(new Set());
  const [hasLoaded, setHasLoaded] = useState(false);
  const [loading, setLoading] = useState(enabled);

  useEffect(() => {
    sessionStorage.setItem(filtersKey, JSON.stringify({ conditions: filterConditions }));
  }, [filtersKey, filterConditions]);

  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    api.getReviewStats(runId)
      .then((stats) => alive && setReviewStats(stats))
      .catch(() => alive && setReviewStats(null));
    return () => {
      alive = false;
    };
  }, [runId, enabled]);

  const needsPendingQueue = filterConditions.some(
    (condition) =>
      condition.field === "review" &&
      String(condition.value ?? "") === "pending" &&
      isActiveCaseFilter(condition)
  );

  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    setHasLoaded(false);
    setLoading(true);
    api.listCaseResults(runId, { limit: CASE_LIST_LIMIT })
      .then((items) => {
        if (!alive) return;
        setCases(items);
        setHasLoaded(true);
      })
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [runId, enabled]);

  useEffect(() => {
    if (!enabled || !needsPendingQueue) {
      setQueueIds(new Set());
      return;
    }
    let alive = true;
    api
      .getReviewQueue(runId, {})
      .then((q) => alive && setQueueIds(new Set(q.map((it) => it.sample_id))))
      .catch(() => alive && setQueueIds(new Set()));
    return () => {
      alive = false;
    };
  }, [runId, enabled, needsPendingQueue]);

  const shownCases = useMemo(
    () => filterCaseRows(cases, filterConditions, queueIds, failureTagLabel),
    [cases, failureTagLabel, filterConditions, queueIds]
  );
  const filterValueOptions = useMemo(
    () => buildCaseFilterValueOptions(cases, failureTagLabel),
    [cases, failureTagLabel]
  );

  const activeFilterCount = filterConditions.filter(isActiveCaseFilter).length;

  const resetFilters = () => {
    setFilterConditions([]);
  };

  return {
    cases,
    shownCases,
    filterConditions,
    setFilterConditions,
    filterValueOptions,
    reviewStats,
    queueIds,
    loading: loading || (enabled && !hasLoaded),
    activeFilterCount,
    resetFilters,
  };
}
