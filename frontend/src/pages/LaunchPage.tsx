import { type ReactNode } from "react";
import {
  Button,
  Checkbox,
  Col,
  Divider,
  Form,
  Input,
  InputNumber,
  Radio,
  Row,
  Select,
} from "antd";
import { RocketOutlined } from "@ant-design/icons";
import { DashboardPageShell } from "../components/DashboardPageShell";
import { AsyncLoadError } from "../components/AsyncLoadError";
import { LaunchJudgeFields } from "../components/LaunchJudgeFields";
import { useLaunchPage } from "../hooks/useLaunchPage";

function FieldHint({ children }: { children: ReactNode }) {
  return <p className="dash-field-hint">{children}</p>;
}
export default function LaunchPage() {
  const lp = useLaunchPage();
  const judgeEnabled = Form.useWatch("judge_enabled", lp.form) ?? true;
  const evaluationMode =
    Form.useWatch("evaluation_mode", lp.form) ?? "single_turn";

  return (
    <DashboardPageShell
      centered
      title="发起评测"
      sub="选择 benchmark 与判分模型，配置运行参数后启动一次新的评测 run"
    >
      <div className="dash-launch">
        {lp.loadError ? (
          <AsyncLoadError
            message={lp.loadError}
            onRetry={lp.reloadLaunchData}
          />
        ) : (
          <Form
            form={lp.form}
            layout="vertical"
            className="dash-launch-form"
            onFinish={lp.onFinish}
            initialValues={{
              judge_enabled: true,
              evaluation_mode: "single_turn",
              enable_rag: true,
              enable_system_prompt: true,
              repeat: 1,
              limit: 0,
              scoring_standard: "cx_eight_dimension",
            }}
            requiredMark
          >
            <div className="dash-form-card dash-launch-card">
              <section className="dash-form-section">
                <h3 className="dash-form-card__title">基础配置</h3>
                <p className="dash-form-card__desc">
                  选择要跑的用例集与运行参数；benchmark 选定后可选 Level 子集。
                </p>

                <Form.Item
                  name="benchmark_id"
                  label="Benchmark 用例集"
                  rules={[{ required: true, message: "请选择 benchmark" }]}
                  extra={
                    <FieldHint>
                      评测将使用该 benchmark 中的全部或部分用例。
                    </FieldHint>
                  }
                >
                  <Select
                    size="large"
                    placeholder="选择评测用例集"
                    onChange={lp.onBenchmarkChange}
                    options={lp.benchmarks.map((b) => ({
                      value: b.id,
                      label: `${b.name}（${b.case_count} 条）`,
                    }))}
                  />
                </Form.Item>

                <Form.Item
                  name="run_name"
                  label="Run 名称"
                  extra={
                    <FieldHint>
                      可选；留空则由系统自动命名。仅支持字母、数字、下划线。
                    </FieldHint>
                  }
                >
                  <Input
                    size="large"
                    placeholder="如 doubao_breast_cancer"
                    maxLength={80}
                    showCount
                  />
                </Form.Item>

                <Form.Item
                  name="evaluation_mode"
                  label="对话评测模式"
                  extra={
                    <FieldHint>
                      单轮使用 main 的固定 turns
                      逻辑；多轮启用本分支的语义追问与用户模拟。
                    </FieldHint>
                  }
                >
                  <Radio.Group
                    className="dash-option-cards dash-evaluation-mode"
                    optionType="button"
                    buttonStyle="solid"
                  >
                    <Radio.Button value="single_turn">
                      单轮对话评测（main 逻辑）
                    </Radio.Button>
                    <Radio.Button value="multi_turn">
                      多轮对话评测（动态逻辑）
                    </Radio.Button>
                  </Radio.Group>
                </Form.Item>

                {evaluationMode === "multi_turn" && (
                  <Form.Item
                    name="user_simulator_model_id"
                    label="语义追问模型"
                    extra={
                      <FieldHint>
                        用于识别 Agent
                        的语义追问并生成未预设的用户回复；不选则使用 config.yaml
                        的默认模型。
                      </FieldHint>
                    }
                  >
                    <Select
                      size="large"
                      allowClear
                      showSearch
                      optionFilterProp="label"
                      placeholder="选择已配置的模型（可选）"
                      options={lp.judgeModels.map((m) => ({
                        value: m.id,
                        label: `${m.name} · ${m.model}${m.has_api_key ? "" : "（未配 Key）"}`,
                      }))}
                    />
                  </Form.Item>
                )}

                <Form.Item
                  name="enable_system_prompt"
                  label="cx-agent 系统提示词"
                  extra={
                    <FieldHint>
                      关闭后 cx-agent
                      不向模型发送系统角色提示词，用于对照验证模型原生能力；默认开启。
                    </FieldHint>
                  }
                >
                  <Radio.Group
                    className="dash-option-cards"
                    optionType="button"
                    buttonStyle="solid"
                  >
                    <Radio.Button value={true}>启用系统提示词</Radio.Button>
                    <Radio.Button value={false}>不启用系统提示词</Radio.Button>
                  </Radio.Group>
                </Form.Item>

                <Form.Item
                  name="enable_rag"
                  label="医学文献 RAG 召回"
                  extra={
                    <FieldHint>
                      开启后允许被测 Agent
                      调用医学文献知识库；关闭时不暴露该工具。不会影响用户画像、长期记忆和历史对话；默认开启。
                    </FieldHint>
                  }
                >
                  <Radio.Group
                    className="dash-option-cards"
                    optionType="button"
                    buttonStyle="solid"
                  >
                    <Radio.Button value={false}>不启用 RAG</Radio.Button>
                    <Radio.Button value={true}>启用 RAG</Radio.Button>
                  </Radio.Group>
                </Form.Item>

                <Row gutter={16}>
                  <Col xs={24} sm={12}>
                    <Form.Item
                      name="repeat"
                      label="重复次数（N-runs voting）"
                      extra={
                        <FieldHint>
                          同一用例重复跑 N 次，按多数票汇总稳定性。
                        </FieldHint>
                      }
                    >
                      <InputNumber
                        min={1}
                        size="large"
                        style={{ width: "100%" }}
                      />
                    </Form.Item>
                  </Col>
                  <Col xs={24} sm={12}>
                    <Form.Item
                      name="limit"
                      label="限制条数"
                      extra={
                        <FieldHint>
                          0 表示跑 benchmark 内全部用例；调试用可设小值。
                        </FieldHint>
                      }
                    >
                      <InputNumber
                        min={0}
                        size="large"
                        style={{ width: "100%" }}
                      />
                    </Form.Item>
                  </Col>
                </Row>

                <Form.Item
                  name="levels"
                  label="Level 筛选"
                  extra={
                    <FieldHint>
                      {lp.selectedBenchmark
                        ? "不选则运行该 benchmark 下全部 Level。"
                        : "请先选择 benchmark，再勾选要跑的 Level。"}
                    </FieldHint>
                  }
                >
                  {lp.levelOptions.length > 0 ? (
                    <Checkbox.Group
                      className="dash-option-cards"
                      disabled={!lp.selectedBenchmark}
                    >
                      {lp.levelOptions.map((opt) => (
                        <Checkbox
                          key={opt.value}
                          value={opt.value}
                          className="dash-option-card"
                        >
                          <span className="dash-option-card__body">
                            <span className="dash-option-card__title">
                              {opt.label}
                            </span>
                            <span className="dash-option-card__desc">
                              仅跑该难度档位的用例 · {opt.count} 题
                            </span>
                          </span>
                        </Checkbox>
                      ))}
                    </Checkbox.Group>
                  ) : (
                    <div className="dash-option-empty">
                      {lp.selectedBenchmark
                        ? "该 benchmark 无 level 字段"
                        : "选择 benchmark 后显示可选 Level"}
                    </div>
                  )}
                </Form.Item>
              </section>

              <Divider className="dash-launch-divider" />

              <LaunchJudgeFields lp={lp} judgeEnabled={judgeEnabled} />

              <div className="dash-form-footer">
                <Button
                  type="primary"
                  size="large"
                  htmlType="submit"
                  loading={lp.submitting}
                  icon={<RocketOutlined />}
                >
                  发起评测
                </Button>
              </div>
            </div>
          </Form>
        )}
      </div>
    </DashboardPageShell>
  );
}
