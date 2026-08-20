import { DIM_LABEL, EVALUATION_DIMENSIONS } from "../labels";
import type { JsonObject } from "../api";

type CaseRecord = JsonObject;

export interface CrossDimensionWarning {
  kind: "ownership" | "duplicate";
  message: string;
}

interface CriterionEntry {
  dimension: string;
  text: string;
  source: string;
}

const OWNER_CLUES: Array<{ dimension: string; pattern: RegExp }> = [
  {
    dimension: "medical_safety",
    pattern: /(立即|尽快|及时).{0,5}(就医|急诊)|拨打\s*120|停药|改药|加量|减量|调整剂量|危险信号|红旗|就医时效/,
  },
  {
    dimension: "professional_accuracy",
    pattern: /医学事实|事实准确|检查结果|报告解读|循证|专业术语|诊断边界|治疗知识|药物机制|概率依据/,
  },
  {
    dimension: "executability",
    pattern: /具体(步骤|时间|频次|数量|处理方法)|准备(资料|材料)|联系(谁|对象)|反馈时机|操作步骤/,
  },
];

const EMPATHY_PURPOSE_PATTERN = /安抚|共情|理解|承接.{0,6}(情绪|焦虑|担心|恐惧)|情绪支持|语气|接纳|不放大.{0,6}(紧张|恐慌)/;

function list(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).map((item) => item.trim()).filter(Boolean);
  return value == null || String(value).trim() === "" ? [] : [String(value).trim()];
}

function entries(caseData: CaseRecord): CriterionEntry[] {
  const evaluation = caseData?.evaluation || {};
  const dimensionCriteria = evaluation.dimension_criteria || {};
  const result: CriterionEntry[] = [];
  for (const dimension of EVALUATION_DIMENSIONS) {
    const raw = dimensionCriteria[dimension];
    const criteria = Array.isArray(raw) ? raw : raw?.criteria;
    list(criteria).forEach((text, index) => result.push({
      dimension,
      text,
      source: `${DIM_LABEL[dimension]}评测要求 ${index + 1}`,
    }));
  }
  (Array.isArray(evaluation.guidelines) ? evaluation.guidelines : []).forEach(
    (guideline: CaseRecord, index: number) => {
      const dimension = String(guideline?.dimension || "");
      list(guideline?.criteria ?? guideline?.criterion).forEach((text, criterionIndex) => {
        result.push({
          dimension,
          text,
          source: `指南扣分点 ${index + 1} / 检查点 ${criterionIndex + 1}`,
        });
      });
    },
  );
  return result;
}

function normalizedChars(text: string): Set<string> {
  const normalized = text
    .replace(/[，。；：、！？,.!?;:\s（）()“”"'《》【】\u005B\u005D]/g, "")
    .replace(/回答|用户|需要|应当|应该|必须|不得|建议|说明|提供|具体|相关|信息|如果|若|该/g, "");
  const grams = new Set<string>();
  for (let index = 0; index < normalized.length - 1; index += 1) {
    grams.add(normalized.slice(index, index + 2));
  }
  return grams;
}

function similarity(left: string, right: string): number {
  const a = normalizedChars(left);
  const b = normalizedChars(right);
  if (a.size < 5 || b.size < 5) return 0;
  const intersection = [...a].filter((value) => b.has(value)).length;
  return intersection / Math.min(a.size, b.size);
}

/**
 * 给 Benchmark 作者的非阻断审查提示。
 *
 * 这里只报告高置信度的主责错位和跨维度近似重复，最终仍由作者结合两条要求的
 * 独立证据与独立影响决定是否迁移或保留。
 */
export function reviewCrossDimensionCriteria(caseData: CaseRecord): CrossDimensionWarning[] {
  const all = entries(caseData);
  const warnings: CrossDimensionWarning[] = [];

  all.forEach((entry) => {
    const clue = OWNER_CLUES.find(({ pattern }) => pattern.test(entry.text));
    if (!clue || clue.dimension === entry.dimension) return;
    // “给出紧急建议时承接用户焦虑”描述的是情绪处理方式，仍可由共情主责；
    // 纯粹要求何时/如何就医的条目则继续提示迁移到医学安全性。
    if (
      entry.dimension === "empathy"
      && clue.dimension === "medical_safety"
      && EMPATHY_PURPOSE_PATTERN.test(entry.text)
    ) return;
    warnings.push({
      kind: "ownership",
      message: `${entry.source}包含“${entry.text}”，主责更接近${DIM_LABEL[clue.dimension]}，建议迁移后再保存。`,
    });
  });

  for (let leftIndex = 0; leftIndex < all.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < all.length; rightIndex += 1) {
      const left = all[leftIndex];
      const right = all[rightIndex];
      if (!left.dimension || !right.dimension || left.dimension === right.dimension) continue;
      if (similarity(left.text, right.text) < 0.68) continue;
      warnings.push({
        kind: "duplicate",
        message: `${left.source}与${right.source}描述高度相似。若两者依赖同一回答证据且造成同一影响，请只保留在唯一主责维度；只有证据和影响都独立时才分别扣分。`,
      });
    }
  }

  return [...new Map(warnings.map((warning) => [warning.message, warning])).values()];
}
