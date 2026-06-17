import { useEffect, useState } from "react";
import { message } from "antd";
import { api } from "../api/index";
import { formatApiError } from "../utils/apiError";
import { useAsyncData } from "./useAsyncData";

export function useReleaseThresholdsPage() {
  const { data: rows, loading, error, reload } = useAsyncData(() => api.getReleaseThresholds(), []);
  const [draft, setDraft] = useState<Record<string, number>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (rows) {
      setDraft(Object.fromEntries(rows.map((r) => [r.profile, r.effective])));
    }
  }, [rows]);

  const save = async () => {
    if (!rows) return;
    setSaving(true);
    try {
      const overrides: Record<string, number> = {};
      for (const r of rows) overrides[r.profile] = draft[r.profile];
      const data = await api.putReleaseThresholds(overrides);
      setDraft(Object.fromEntries(data.map((r) => [r.profile, r.effective])));
      reload();
      message.success("上线判定阈值已保存（对之后发起的新评测与重判生效）");
    } catch (e: unknown) {
      message.error(formatApiError(e, "保存失败"));
    } finally {
      setSaving(false);
    }
  };

  const resetProfile = (profile: string, defaultThreshold: number) => {
    setDraft((d) => ({ ...d, [profile]: defaultThreshold }));
  };

  const setProfileDraft = (profile: string, value: number) => {
    setDraft((d) => ({ ...d, [profile]: value }));
  };

  return {
    rows: rows ?? [],
    draft,
    loading,
    loadError: error,
    reload,
    saving,
    save,
    resetProfile,
    setProfileDraft,
  };
}
