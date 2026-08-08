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
  runStatus?: string,
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
    const refresh = () => {
      if (document.visibilityState !== "visible") return;
      api.getReviewStats(runId)
        .then((stats) => alive && setReviewStats(stats))
        .catch(() => alive && setReviewStats(null));
    };
    refresh();
    const active = runStatus === "running" || runStatus === "pending";
    const timer = active ? window.setInterval(refresh, 2000) : null;
    return () => {
      alive = false;
      if (timer !== null) window.clearInterval(timer);
    };
  }, [runId, enabled, runStatus]);

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
    const refresh = (showLoading = false) => {
      if (document.visibilityState !== "visible") return;
      if (showLoading) setLoading(true);
      api.listCaseResults(runId, { limit: CASE_LIST_LIMIT })
        .then((items) => {
          if (!alive) return;
          setCases(items);
          setHasLoaded(true);
        })
        .catch(() => undefined)
        .finally(() => alive && setLoading(false));
    };
    refresh(true);
    const active = runStatus === "running" || runStatus === "pending";
    const timer = active ? window.setInterval(() => refresh(false), 2000) : null;
    const onVisibility = () => {
      if (document.visibilityState === "visible") refresh(false);
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      alive = false;
      if (timer !== null) window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [runId, enabled, runStatus]);

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
