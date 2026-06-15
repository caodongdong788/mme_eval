import { useState } from "react";
import { Modal, message } from "antd";
import { api, type Benchmark } from "../api";
import { formatApiError } from "../utils/apiError";

interface SaveAsArgs {
  name: string;
  description: string;
  onSuccess: (bm: Benchmark) => void;
}

interface OverwriteArgs {
  confirmContent: string;
  onSuccess: (bm: Benchmark) => void;
}

interface Options {
  benchmarkId?: number | null;
  getYamlText: () => string;
}

// 改判据 YAML 的两种落地动作（另存为新 benchmark / 覆盖当前 benchmark）的共享流程：
// 集中处理 benchmarkId 校验、saving 状态、API 调用与错误提示；页面专属文案/善后经回调注入，
// 既消除两处重复的 try/catch 样板，又保持各页原有提示文案与行为不变。
export function useBenchmarkYamlActions({ benchmarkId, getYamlText }: Options) {
  const [saving, setSaving] = useState(false);

  const saveAsBenchmark = async ({ name, description, onSuccess }: SaveAsArgs) => {
    if (!benchmarkId) {
      message.error("该评测未关联 benchmark，无法另存");
      return;
    }
    if (!name.trim()) {
      message.error("请填写新 benchmark 名称");
      return;
    }
    setSaving(true);
    try {
      const bm = await api.deriveBenchmarkFromYaml(benchmarkId, {
        name: name.trim(),
        description,
        yaml_text: getYamlText(),
      });
      onSuccess(bm);
    } catch (e) {
      message.error(formatApiError(e, "另存失败"));
    } finally {
      setSaving(false);
    }
  };

  const overwriteBenchmark = ({ confirmContent, onSuccess }: OverwriteArgs) => {
    if (!benchmarkId) {
      message.error("该评测未关联 benchmark，无法覆盖");
      return;
    }
    const bid = benchmarkId;
    Modal.confirm({
      title: "覆盖当前 benchmark？",
      content: confirmContent,
      okText: "确认覆盖",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        setSaving(true);
        try {
          const bm = await api.overwriteBenchmarkFromYaml(bid, {
            yaml_text: getYamlText(),
          });
          onSuccess(bm);
        } catch (e) {
          message.error(formatApiError(e, "覆盖失败"));
        } finally {
          setSaving(false);
        }
      },
    });
  };

  return { saving, saveAsBenchmark, overwriteBenchmark };
}
