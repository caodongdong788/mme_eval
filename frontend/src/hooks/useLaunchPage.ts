import { useEffect, useMemo, useState } from "react";
import { Form, message } from "antd";
import { useNavigate } from "react-router-dom";
import {
  api,
  Benchmark,
  CaseBrief,
  JudgeModel,
  RunCreatePayload,
  selectableBenchmarks,
} from "../api/index";
import { formatApiError } from "../utils/apiError";
import { computeLaunchCaseCount, countCasesByLevel } from "../utils/launchCaseCount";
import { useAsyncData } from "./useAsyncData";

export interface LaunchLevelOption {
  value: string;
  label: string;
  count: number;
}

export function useLaunchPage() {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [casesLoading, setCasesLoading] = useState(false);
  const [benchmarkCases, setBenchmarkCases] = useState<CaseBrief[]>([]);
  const [levelOptions, setLevelOptions] = useState<LaunchLevelOption[]>([]);

  const {
    data: benchmarks,
    loading: benchmarksLoading,
    error: benchmarksError,
    reload: reloadLaunchData,
  } = useAsyncData(() => api.listBenchmarks().then(selectableBenchmarks), []);
  const { data: judgeModels, error: judgeModelsError } = useAsyncData(
    () => api.listJudgeModels(),
    []
  );
  const { data: judgeDefaults, error: judgeDefaultsError } = useAsyncData(
    () => api.getJudgeDefaults(),
    []
  );

  const loadError = benchmarksError ?? judgeModelsError ?? judgeDefaultsError;

  const judgeDefaultModel = judgeDefaults?.model?.trim() || null;
  const defaultJudgeModelId = useMemo(() => {
    if (!judgeDefaults) return undefined;
    return (judgeModels ?? []).find(
      (model) =>
        model.model === judgeDefaults.model &&
        model.base_url === judgeDefaults.base_url &&
        model.provider === judgeDefaults.provider
    )?.id;
  }, [judgeDefaults, judgeModels]);

  useEffect(() => {
    if (defaultJudgeModelId && !form.getFieldValue("judge_model_id")) {
      form.setFieldValue("judge_model_id", defaultJudgeModelId);
    }
  }, [defaultJudgeModelId, form]);

  const benchmarkId = Form.useWatch("benchmark_id", form);
  const selectedLevels = Form.useWatch("levels", form) ?? [];
  const limit = Form.useWatch("limit", form) ?? 0;

  const selectedBenchmark = useMemo(
    () => (benchmarks ?? []).find((b) => b.id === benchmarkId),
    [benchmarks, benchmarkId]
  );

  const estimatedCaseCount = useMemo(
    () => computeLaunchCaseCount(benchmarkCases, selectedLevels, limit),
    [benchmarkCases, selectedLevels, limit]
  );

  const onBenchmarkChange = async (id: number) => {
    const benchmark = (benchmarks ?? []).find((item) => item.id === id);
    form.setFieldValue("evaluation_mode", benchmark?.default_evaluation_mode || "single_turn");
    form.setFieldValue("levels", []);
    setLevelOptions([]);
    setBenchmarkCases([]);
    setCasesLoading(true);
    try {
      const cases = await api.getBenchmarkCases(id);
      setBenchmarkCases(cases);
      const byLevel = countCasesByLevel(cases);
      const levels = Object.keys(byLevel).sort();
      setLevelOptions(levels.map((l) => ({ value: l, label: l, count: byLevel[l] })));
    } catch (e: unknown) {
      message.error(formatApiError(e, "加载用例失败"));
    } finally {
      setCasesLoading(false);
    }
  };

  const onFinish = async (values: Record<string, unknown>) => {
    const payload: RunCreatePayload = {
      benchmark_id: values.benchmark_id as number,
      run_name: (values.run_name as string) || undefined,
      evaluation_mode: (values.evaluation_mode as "single_turn" | "multi_turn") || "single_turn",
      levels: (values.levels as string[]) || [],
      limit: (values.limit as number) || 0,
      repeat: (values.repeat as number) || undefined,
      judge: { enabled: values.judge_enabled as boolean },
      adapter: { enable_rag: values.enable_rag as boolean },
      judge_model_id: (values.judge_model_id as number) || undefined,
      user_simulator_model_id:
        values.evaluation_mode === "multi_turn"
          ? (values.user_simulator_model_id as number) || undefined
          : undefined,
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
    defaultJudgeModelId,
    benchmarksLoading,
    loadError,
    reloadLaunchData,
    submitting,
    casesLoading,
    levelOptions,
    estimatedCaseCount,
    selectedBenchmark: selectedBenchmark as Benchmark | undefined,
    onBenchmarkChange,
    onFinish,
  };
}
