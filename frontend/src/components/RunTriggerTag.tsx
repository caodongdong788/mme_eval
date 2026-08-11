import { Tag } from "antd";
import type { RunSummary } from "../api";

const labels: Record<RunSummary["trigger_type"], { label: string; color: string }> = {
  manual: { label: "人工触发", color: "blue" },
  scheduled: { label: "定时任务触发", color: "purple" },
  open_api: { label: "Open API 触发", color: "cyan" },
};

export function RunTriggerTag({ type }: { type?: RunSummary["trigger_type"] | null }) {
  const item = labels[type ?? "manual"] ?? labels.manual;
  return <Tag color={item.color}>{item.label}</Tag>;
}
