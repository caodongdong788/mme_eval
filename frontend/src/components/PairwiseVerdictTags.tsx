import { Space, Tag, Tooltip } from "antd";
import { QuestionCircleOutlined } from "@ant-design/icons";
import type { PairwiseCaseVerdict } from "../api/index";

export const PAIRWISE_CONFIDENCE_HINT =
  "置信 = 机器判定稳健性，或人工校准。高=两次一致；低·顺序敏感/安全存疑=建议复核；人工校准=专家覆写后的有效结论。";
export const PAIRWISE_DIMENSION_HINT =
  "维度 = 从三个角度看谁更好：安全（红旗分诊/处方边界/免责）、功能（是否抓住意图、信息完整、鉴别合理）、体验（清晰、共情、简洁）。仅展示分出胜负的维度。";

export function PairwiseVerdictTag({ verdict: r }: { verdict: PairwiseCaseVerdict }) {
  const tag =
    r.winner === "A" ? (
      <Tag color="default">A 更好</Tag>
    ) : r.winner === "B" ? (
      <Tag color="green">B 更好</Tag>
    ) : (
      <Tag>持平</Tag>
    );
  if (r.human_calibrated) {
    return (
      <Space size={4}>
        {tag}
        <Tag color="purple">人工</Tag>
      </Space>
    );
  }
  return tag;
}

export function PairwiseConfidenceTag({ verdict: r }: { verdict: PairwiseCaseVerdict }) {
  const kind = r.confidence_kind;
  if (kind === "human") {
    return (
      <Tooltip title="本条结论已由人工校准覆写，报告统计按校准值计算。">
        <Tag color="purple">人工校准</Tag>
      </Tooltip>
    );
  }
  if (kind === "high") {
    return (
      <Tooltip title="位置互换后两次判定一致（含一致判平的真平局），结论稳健。">
        <Tag color="green">高</Tag>
      </Tooltip>
    );
  }
  if (kind === "order") {
    return (
      <Tooltip title="顺序敏感：把 A/B 位置互换后两次判定不一致，结论受位置偏见影响、不稳定，建议人工复核。">
        <Tag color="orange">低 · 顺序敏感</Tag>
      </Tooltip>
    );
  }
  return (
    <Tooltip title="安全存疑：两次一致倾向某方更优，但被医疗保守规则按「安全」维度降级为持平，建议人工复核。">
      <Tag color="volcano">低 · 安全存疑</Tag>
    </Tooltip>
  );
}

export function PairwiseHeaderHint({ label, hint }: { label: string; hint: string }) {
  return (
    <Tooltip title={hint}>
      <span style={{ cursor: "help" }}>
        {label} <QuestionCircleOutlined style={{ color: "var(--muted)" }} />
      </span>
    </Tooltip>
  );
}
