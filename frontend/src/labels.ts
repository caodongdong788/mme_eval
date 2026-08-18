export const DIM_LABEL: Record<string, string> = {
  medical_safety: "医学安全性",
  professional_accuracy: "专业准确性与边界",
  clinical_inquiry: "临床追问充分性",
  personalization: "个性化相关性",
  plan_feasibility: "方案可行性与依从引导",
  empathy: "被理解与共情",
  executability: "可执行性（可落地感）",
  communication: "沟通体验与继续意愿",
};

export const EVALUATION_DIMENSIONS = [
  "medical_safety",
  "professional_accuracy",
  "clinical_inquiry",
  "personalization",
  "plan_feasibility",
  "empathy",
  "executability",
  "communication",
] as const;

export const EVALUATION_ROLE_ORDER = ["doctor", "nurse", "patient"] as const;
export const EVALUATION_ROLE_LABEL: Record<(typeof EVALUATION_ROLE_ORDER)[number], string> = {
  doctor: "医生端",
  nurse: "护士端",
  patient: "患者端",
};
export const EVALUATION_DIMENSION_ROLE: Record<(typeof EVALUATION_DIMENSIONS)[number], (typeof EVALUATION_ROLE_ORDER)[number]> = {
  medical_safety: "doctor",
  professional_accuracy: "doctor",
  clinical_inquiry: "doctor",
  personalization: "nurse",
  plan_feasibility: "nurse",
  empathy: "patient",
  executability: "patient",
  communication: "patient",
};

export const STABILITY_LABEL: Record<string, string> = {
  stable_pass: "稳过",
  flaky: "抖动",
  stable_fail: "稳挂",
};
