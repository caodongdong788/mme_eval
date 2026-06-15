import type { JudgeDefaults } from "../api/index";

/** 将 config.yaml 默认判分模型格式化为展示文案。 */
export function formatJudgeDefaultLabel(defaults?: JudgeDefaults | null): string | null {
  if (!defaults?.model?.trim()) return null;
  const provider = defaults.provider?.trim();
  return provider ? `${provider} · ${defaults.model}` : defaults.model;
}
