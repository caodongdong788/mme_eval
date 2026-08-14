import type { ProgressInfo } from "../api";

export function isActiveCaseRetry(
  progress: ProgressInfo,
  sampleId: string | undefined
): boolean {
  if (!sampleId || !["pending", "running"].includes(progress.status)) return false;
  const context = progress.progress?.context;
  if (context?.kind === "case_retry") return context.sample_id === sampleId;
  return context?.kind === "cases_retry" && context.sample_ids?.includes(sampleId) === true;
}
