import { Form, Radio, Select, Switch, Typography } from "antd";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { useLaunchPage } from "../hooks/useLaunchPage";

const { Text } = Typography;

function FieldHint({ children }: { children: ReactNode }) {
  return <p className="dash-field-hint">{children}</p>;
}

function judgeModelHint(lp: ReturnType<typeof useLaunchPage>) {
  const defaultHint = lp.judgeDefaultModel
    ? `默认使用 ${lp.judgeDefaultModel}。`
    : "";
  if (lp.judgeModels.length === 0) {
    return (
      <>
        还没有配置判分模型，去{" "}
        <Link to="/judge-models" className="dash-form__link">
          资源 · 判分模型
        </Link>{" "}
        新增。{defaultHint}
      </>
    );
  }
  return (
    <>可选；不选则{defaultHint || "沿用服务器 config.yaml 默认打分模型。"}</>
  );
}

export function LaunchJudgeFields({
  lp,
  judgeEnabled,
}: {
  lp: ReturnType<typeof useLaunchPage>;
  judgeEnabled: boolean;
}) {
  return (
    <section className="dash-form-section">
      <h3 className="dash-form-card__title">判分配置</h3>
      <p className="dash-form-card__desc">
        配置 LLM-as-Judge 打分模型；关闭后仅跑 bot 留痕，不做自动判分。
      </p>

      <Form.Item
        name="scoring_standard"
        label="评分维度"
        extra={
          <FieldHint>
            选择后会冻结在本次评测中。两套八维都会对当前回答给出分维分数和总分：
            Agent 评测八维用于产品质量与上线门禁；模型对比八维用于模型能力评分。Pairwise
            仅对已完成的评测结果做横向比较。TTFT、延迟和 Token 始终只观测，不参与打分。
          </FieldHint>
        }
      >
        <Radio.Group
          className="dash-option-cards dash-evaluation-mode"
          optionType="button"
          buttonStyle="solid"
        >
          <Radio.Button value="cx_eight_dimension">Agent 评测八维</Radio.Button>
          <Radio.Button value="model_comparison">模型对比八维</Radio.Button>
        </Radio.Group>
      </Form.Item>

      <div className="dash-toggle-card">
        <div>
          <div className="dash-toggle-card__title">启用 LLM 打分</div>
          <div className="dash-toggle-card__desc">
            开启后将对 bot 回复运行固定八维评分和 Case 指南覆盖评分。
          </div>
        </div>
        <Form.Item name="judge_enabled" valuePropName="checked" noStyle>
          <Switch />
        </Form.Item>
      </div>

      <Form.Item
        name="judge_model_id"
        label="打分模型"
        extra={<FieldHint>{judgeModelHint(lp)}</FieldHint>}
        style={{ marginTop: 16 }}
      >
        <Select
          size="large"
          allowClear
          showSearch
          disabled={!judgeEnabled}
          optionFilterProp="label"
          placeholder={
            judgeEnabled ? "选择一个已配置的判分模型" : "已关闭 LLM 打分"
          }
          options={lp.judgeModels.map((model) => ({
            value: model.id,
            label: `${model.name} · ${model.model}${
              model.id === lp.defaultJudgeModelId
                ? "（默认）"
                : model.has_api_key
                  ? ""
                  : "（未配 Key）"
            }`,
          }))}
        />
      </Form.Item>

      {lp.selectedBenchmark ? (
        <div className="dash-launch-summary">
          <Text type="secondary">即将发起：</Text>
          <span className="dash-chip">{lp.selectedBenchmark.name}</span>
          <span className="dash-chip">
            {lp.casesLoading ? "加载中…" : `${lp.estimatedCaseCount} 题`}
          </span>
        </div>
      ) : null}
    </section>
  );
}
