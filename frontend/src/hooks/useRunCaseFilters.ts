import { useEffect, useMemo, useState } from "react";
import { api, CASE_LIST_LIMIT, CaseRow, ReviewStats } from "../api/index";
import {
  CASE_FILTER_FIELDS,
  type CaseFilterCondition,
  buildCaseFilterValueOptions,
  filterCaseRows,
  isActiveCaseFilter,
} from "../utils/caseFilters";
import { usePollingTask } from "./usePollingTask";

function readSavedFilters(filtersKey: string): {
  conditions: CaseFilterCondition[];
} {
  try {
    const raw = sessionStorage.getItem(filtersKey);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed.conditions)) {
        const validFields = new Set(CASE_FILTER_FIELDS.map((field) => field.value));
        return {
          conditions: parsed.conditions.filter(
            (condition: CaseFilterCondition) => validFields.has(condition.field)
          ),
        };
      }
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

  const [cases, setCases] = useState<CaseRow[]>([]);
  const [filterConditions, setFilterConditions] = useState<CaseFilterCondition[]>(
    () => readSavedFilters(filtersKey).conditions
  );
  const [reviewStats, setReviewStats] = useState<ReviewStats | null>(null);
  const [queueIds, setQueueIds] = useState<Set<string>>(new Set());
  const [hasLoaded, setHasLoaded] = useState(false);
  const [loading, setLoading] = useState(enabled);
  const [caseTotal, setCaseTotal] = useState(0);
  const active = runStatus === "running" || runStatus === "pending";

  useEffect(() => {
    sessionStorage.setItem(filtersKey, JSON.stringify({ conditions: filterConditions }));
  }, [filtersKey, filterConditions]);

  usePollingTask(
    async (isCurrent) => {
      try {
        const stats = await api.getReviewStats(runId);
        if (isCurrent()) setReviewStats(stats);
      } catch {
        if (isCurrent()) setReviewStats(null);
      }
    },
    [runId],
    { enabled, intervalMs: active ? 2000 : 60_000 },
  );

  const needsPendingQueue = filterConditions.some(
    (condition) =>
      condition.field === "review" &&
      (Array.isArray(condition.value)
        ? condition.value.includes("pending")
        : condition.value === "pending") &&
      isActiveCaseFilter(condition)
  );

  useEffect(() => {
    if (!enabled) return;
    setHasLoaded(false);
    setLoading(true);
  }, [enabled, runId]);

  usePollingTask(
    async (isCurrent) => {
      try {
        const first = await api.listCaseResults(runId, {
          limit: CASE_LIST_LIMIT,
          offset: 0,
        });
        const items = [...first.items];
        let offset = items.length;
        while (offset < first.total) {
          const page = await api.listCaseResults(runId, {
            limit: CASE_LIST_LIMIT,
            offset,
          });
          if (!page.items.length) break;
          items.push(...page.items);
          offset += page.items.length;
        }
        if (!isCurrent()) return;
        setCases(items);
        setCaseTotal(first.total);
        setHasLoaded(true);
      } finally {
        if (isCurrent()) setLoading(false);
      }
    },
    [runId],
    { enabled, intervalMs: active ? 2000 : 60_000 },
  );

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
    caseTotal,
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
