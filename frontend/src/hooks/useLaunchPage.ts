import { useMemo, useState } from "react";
import { Form, message } from "antd";
import { useNavigate } from "react-router-dom";
import {
  api,
  Benchmark,
  JudgeModel,
  RunCreatePayload,
  selectableBenchmarks,
} from "../api/index";
import { formatApiError } from "../utils/apiError";
import { useAsyncData } from "./useAsyncData";

export function useLaunchPage() {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [levelOptions, setLevelOptions] = useState<{ value: string; label: string }[]>([]);

  const { data: benchmarks } = useAsyncData(
    () => api.listBenchmarks().then(selectableBenchmarks),
    []
  );
  const { data: judgeModels } = useAsyncData(() => api.listJudgeModels(), []);
  const {
    data: judgeDefaults,
  } = useAsyncData(() => api.getJudgeDefaults(), []);

  const judgeDefaultModel = judgeDefaults?.model?.trim() || null;

  const benchmarkId = Form.useWatch("benchmark_id", form);

  const selectedBenchmark = useMemo(
    () => (benchmarks ?? []).find((b) => b.id === benchmarkId),
    [benchmarks, benchmarkId]
  );

  const onBenchmarkChange = async (id: number) => {
    form.setFieldValue("levels", []);
    setLevelOptions([]);
    const cases = await api.getBenchmarkCases(id);
    const levels = Array.from(new Set(cases.map((c) => c.level).filter(Boolean))).sort();
    setLevelOptions(levels.map((l) => ({ value: l, label: l })));
  };

  const onFinish = async (values: Record<string, unknown>) => {
    const payload: RunCreatePayload = {
      benchmark_id: values.benchmark_id as number,
      run_name: (values.run_name as string) || undefined,
      levels: (values.levels as string[]) || [],
      limit: (values.limit as number) || 0,
      repeat: (values.repeat as number) || undefined,
      judge: { enabled: values.judge_enabled as boolean },
      judge_model_id: (values.judge_model_id as number) || undefined,
    };
    setSubmitting(true);
    try {
      const run = await api.createRun(payload);
      message.success(`评测已发起：#${run.id}`);
      navigate(`/runs`);
    } catch (e: unknown) {
      message.error(formatApiError(e, "发起失败"));
    } finally {
      setSubmitting(false);
    }
  };

  return {
    form,
    benchmarks: benchmarks ?? [],
    judgeModels: (judgeModels ?? []) as JudgeModel[],
    judgeDefaultModel,
    submitting,
    levelOptions,
    selectedBenchmark: selectedBenchmark as Benchmark | undefined,
    onBenchmarkChange,
    onFinish,
  };
}
