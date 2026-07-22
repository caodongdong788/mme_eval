import { authApi } from "./auth";
import { benchmarksApi, selectableBenchmarks } from "./benchmarks";
import { configApi } from "./config";
import { dashboardApi } from "./dashboard";
import { FEISHU_LOGIN_URL } from "./client";
import { judgeModelsApi } from "./judgeModels";
import { pairwiseApi } from "./pairwise";
import { runsApi } from "./runs";

export { CASE_LIST_LIMIT } from "./runs";
export * from "./types";
export { FEISHU_LOGIN_URL, selectableBenchmarks };

export const api = {
  ...benchmarksApi,
  ...configApi,
  ...judgeModelsApi,
  ...runsApi,
  ...pairwiseApi,
  ...dashboardApi,
  ...authApi,
};
