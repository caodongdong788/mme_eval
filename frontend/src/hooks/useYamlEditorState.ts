import { useCallback, useState } from "react";
import { message } from "antd";
import { api } from "../api/index";
import { formatApiError } from "../utils/apiError";

function buildYamlName(runName?: string): string {
  return `${runName || "派生"} · 改判据 ${new Date()
    .toISOString()
    .slice(5, 16)
    .replace("T", "-")}`;
}

export function useYamlEditorState(runName?: string) {
  const [yamlOpen, setYamlOpen] = useState(false);
  const [yamlLoading, setYamlLoading] = useState(false);
  const [yamlText, setYamlText] = useState("");
  const [yamlName, setYamlName] = useState("");

  const openFromRun = useCallback(
    async (
      runId: number,
      params: Record<string, unknown>,
      options?: { onBeforeOpen?: () => void; namePrefix?: string }
    ) => {
      setYamlOpen(true);
      setYamlLoading(true);
      setYamlText("");
      options?.onBeforeOpen?.();
      try {
        const res = await api.getRunCasesYaml(runId, params);
        setYamlText(res.yaml_text);
        setYamlName(buildYamlName(options?.namePrefix ?? runName));
      } catch (e: unknown) {
        message.error(formatApiError(e, "加载用例 YAML 失败"));
        setYamlOpen(false);
      } finally {
        setYamlLoading(false);
      }
    },
    [runName]
  );

  return {
    yamlOpen,
    setYamlOpen,
    yamlLoading,
    yamlText,
    setYamlText,
    yamlName,
    setYamlName,
    openFromRun,
  };
}
