import type { ProgressInfo } from "../api";

export function isActiveCaseRetry(
  progress: ProgressInfo,
  sampleId: string | undefined
): boolean {
  if (!sampleId || !["pending", "running"].includes(progress.status)) return false;
  const context = progress.progress?.context;
  return context?.kind === "case_retry" && context.sample_id === sampleId;
}
