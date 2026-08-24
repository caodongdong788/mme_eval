import { SyncOutlined } from "@ant-design/icons";
import { Spin, Tabs } from "antd";
import { useState } from "react";
import { AsyncLoadError } from "../components/AsyncLoadError";
import { DashboardPageShell } from "../components/DashboardPageShell";
import {
  AgentEvaluationStandard,
  ModelComparisonStandard,
} from "../components/EvaluationStandardContent";
import { useEvaluationStandardPage } from "../hooks/useEvaluationStandardPage";

export default function EvaluationStandardPage() {
  const { data, error, loading, reload } = useEvaluationStandardPage();
  const [activeStandard, setActiveStandard] = useState("cx_eight_dimension");

  if (loading) {
    return (
      <div className="evaluation-standard-loading">
        <Spin tip="正在同步评分标准" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <DashboardPageShell title="八维评分标准">
        <AsyncLoadError message="评分标准加载失败" onRetry={reload} />
      </DashboardPageShell>
    );
  }

  return (
    <DashboardPageShell
      title="评分标准"
      sub="Agent 评测八维用于产品质量与上线门禁；模型对比八维用于公平比较不同基座能力。"
      extra={
        <span className="status-dot status-dot--pass evaluation-standard-sync">
          <SyncOutlined />
          已与当前 Judge 同步
        </span>
      }
    >
      <Tabs
        activeKey={activeStandard}
        onChange={setActiveStandard}
        items={[
          { key: "cx_eight_dimension", label: "Agent 评测八维" },
          { key: "model_comparison", label: "模型对比八维" },
        ]}
      />
      {activeStandard === "model_comparison" ? (
        <ModelComparisonStandard standard={data.model_comparison} />
      ) : (
        <AgentEvaluationStandard data={data} />
      )}
    </DashboardPageShell>
  );
}
