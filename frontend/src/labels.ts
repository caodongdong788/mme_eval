// 评分相关的中文标签单一信任源：四模块维度 / 评分档 profile / 稳定性口径。
// 各页面统一从这里 import，禁止再各自复制定义（避免漂移）。
// PROFILE_LABEL 与 server/services/platform_config.PROFILE_LABELS_ZH 保持同步（门禁：npm run check:standards）。

// 四模块维度 key → 中文。pairwise 仅用 safety/function/experience 子集，复用本表无副作用。
export const DIM_LABEL: Record<string, string> = {
  safety: "安全",
  compliance: "合规",
  function: "功能",
  experience: "体验",
  inquiry: "问诊",
};

// 评分档（profile）→ 中文，未知回退原文。与 server/services/platform_config.PROFILE_LABELS_ZH 保持同步。
export const PROFILE_LABEL: Record<string, string> = {
  default: "默认（兜底）",
  adversarial: "对抗",
  red_flag: "红旗分诊",
  knowledge: "知识科普",
  rehab: "康复随访",
  population: "人群特异",
  agent: "Agent 问诊",
};

// 稳定性（N-runs 投票口径）→ 中文。
export const STABILITY_LABEL: Record<string, string> = {
  stable_pass: "稳过",
  flaky: "抖动",
  stable_fail: "稳挂",
};
