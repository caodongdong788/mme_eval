import { useEffect, useMemo, useState } from "react";
import { message } from "antd";
import { api, ScoringProfileItem, ScoringProfileSnapshot } from "../api/index";
import { formatApiError } from "../utils/apiError";
import { useAsyncData } from "./useAsyncData";

export type ProfileDraft = ScoringProfileSnapshot;

function snapshotFromEffective(row: ScoringProfileItem): ProfileDraft {
  const e = row.effective;
  return {
    module_max: { ...e.module_max },
    function_deduction: e.function_deduction,
    safety_function_deduction: e.safety_function_deduction,
    min_composite: e.min_composite,
    gates: { ...e.gates },
    max_total: e.max_total,
    pass_rule_type: e.pass_rule_type,
  };
}

function draftsEqual(a: ProfileDraft, b: ProfileDraft): boolean {
  const keys = new Set([...Object.keys(a.module_max), ...Object.keys(b.module_max)]);
  for (const k of keys) {
    if (Math.abs((a.module_max[k] ?? 0) - (b.module_max[k] ?? 0)) > 1e-6) return false;
  }
  if (Math.abs(a.function_deduction - b.function_deduction) > 1e-6) return false;
  if (
    Math.abs(a.safety_function_deduction - b.safety_function_deduction) > 1e-6
  ) {
    return false;
  }
  if (Math.abs(a.min_composite - b.min_composite) > 1e-6) return false;
  return JSON.stringify(a.gates) === JSON.stringify(b.gates);
}

export function isProfileCustomized(row: ScoringProfileItem, draft: ProfileDraft): boolean {
  return !draftsEqual(draft, snapshotFromEffective({ ...row, effective: row.defaults }));
}

export function useScoringProfilesPage() {
  const { data: rows, loading, error, reload } = useAsyncData(
    () => api.getScoringProfiles(),
    []
  );
  const [draft, setDraft] = useState<Record<string, ProfileDraft>>({});
  const [saving, setSaving] = useState(false);
  const [activeProfile, setActiveProfile] = useState<string>("knowledge");

  useEffect(() => {
    if (rows) {
      setDraft(Object.fromEntries(rows.map((r) => [r.profile, snapshotFromEffective(r)])));
      if (!rows.some((r) => r.profile === activeProfile) && rows[0]) {
        setActiveProfile(rows[0].profile);
      }
    }
  }, [rows]);

  const customizedCount = useMemo(() => {
    if (!rows) return 0;
    return rows.filter((r) => draft[r.profile] && isProfileCustomized(r, draft[r.profile])).length;
  }, [rows, draft]);

  const setProfileDraft = (profile: string, patch: Partial<ProfileDraft>) => {
    setDraft((d) => ({
      ...d,
      [profile]: { ...d[profile], ...patch },
    }));
  };

  const resetProfile = (row: ScoringProfileItem) => {
    setProfileDraft(row.profile, snapshotFromEffective({ ...row, effective: row.defaults }));
  };

  const save = async () => {
    if (!rows) return;
    setSaving(true);
    try {
      const overrides: Record<string, Record<string, unknown> | null> = {};
      for (const row of rows) {
        const d = draft[row.profile];
        if (!d || !isProfileCustomized(row, d)) {
          overrides[row.profile] = null;
          continue;
        }
        const payload: Record<string, unknown> = {
          module_max: d.module_max,
          function_deduction: d.function_deduction,
        };
        if (
          Math.abs(d.safety_function_deduction - row.defaults.safety_function_deduction) > 1e-6
        ) {
          payload.safety_function_deduction = d.safety_function_deduction;
        }
        if (row.defaults.pass_rule_type === "threshold") {
          payload.min_composite = d.min_composite;
          payload.gates = d.gates;
        }
        overrides[row.profile] = payload;
      }
      const data = await api.putScoringProfiles(overrides);
      setDraft(Object.fromEntries(data.map((r) => [r.profile, snapshotFromEffective(r)])));
      message.success("评分配置已保存（对之后发起的新评测与重判生效）");
    } catch (e: unknown) {
      message.error(formatApiError(e, "保存失败"));
    } finally {
      setSaving(false);
    }
  };

  return {
    rows: rows ?? [],
    draft,
    loading,
    loadError: error,
    reload,
    saving,
    save,
    activeProfile,
    setActiveProfile,
    setProfileDraft,
    resetProfile,
    customizedCount,
  };
}
