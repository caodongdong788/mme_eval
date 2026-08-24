import { Space, Tag, Tooltip } from "antd";
import { QuestionCircleOutlined } from "@ant-design/icons";
import type { PairwiseCaseVerdict } from "../api/index";

export const PAIRWISE_CONFIDENCE_HINT =
  "置信 = 机器判定稳健性，或人工校准。高=交换 A/B 位置后整体与各维度判断一致；低·顺序敏感=位置变化会影响判断；安全存疑仅适用于 CX 八维评分；人工校准=专家覆写后的有效结论。";
export const PAIRWISE_DIMENSION_HINT =
  "维度 = 按该评测冻结的评分标准逐项比较 A/B。模型对比八维允许标记为“不适用”；仅展示分出胜负或不适用的维度。TTFT、延迟和 Token 只观测，不参与胜负。";

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
      <Tooltip title="位置互换后两次整体与八维判断一致（含一致判平的真平局），结论稳健。">
        <Tag color="green">高</Tag>
      </Tooltip>
    );
  }
  if (kind === "order") {
    return (
      <Tooltip title="顺序敏感：把 A/B 位置互换后，两次整体或任一维度判断不一致；平台仍按八维结果给出总胜方，但建议人工复核。">
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
