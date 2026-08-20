import { useEffect, useState } from "react";
import { api } from "../api";
import { useAsyncData } from "./useAsyncData";

export function useRegressionTrends() {
  const {
    data: schedules,
    loading: schedulesLoading,
    error: schedulesError,
    reload: reloadSchedules,
  } = useAsyncData(() => api.listScheduledEvaluations(), []);
  const [scheduleId, setScheduleId] = useState<number>();

  useEffect(() => {
    if (schedules?.length && scheduleId == null) setScheduleId(schedules[0].id);
  }, [schedules, scheduleId]);

  const {
    data: regression,
    loading: regressionLoading,
    error: regressionError,
    reload: reloadRegression,
  } = useAsyncData(
    () => (scheduleId == null ? Promise.resolve(null) : api.getRegressionTrends(scheduleId)),
    [scheduleId]
  );

  const reload = () => {
    reloadSchedules();
    if (scheduleId != null) reloadRegression();
  };

  return {
    schedules: schedules ?? [],
    schedulesLoading,
    scheduleId,
    setScheduleId,
    points: regression?.points ?? [],
    regressionLoading,
    error: schedulesError || regressionError,
    reload,
  };
}
