import { type ReactNode } from "react";
import {
  Button,
  Checkbox,
  Col,
  Divider,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Switch,
  Typography,
} from "antd";
import { RocketOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import { DashboardPageShell } from "../components/DashboardPageShell";
import { AsyncLoadError } from "../components/AsyncLoadError";
import { useLaunchPage } from "../hooks/useLaunchPage";

const { Text } = Typography;

function FieldHint({ children }: { children: ReactNode }) {
  return <p className="dash-field-hint">{children}</p>;
}

function judgeModelHint(lp: ReturnType<typeof useLaunchPage>) {
  const defaultHint = lp.judgeDefaultModel ? `默认使用 ${lp.judgeDefaultModel}。` : "";
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
  return <>可选；不选则{defaultHint || "沿用服务器 config.yaml 默认打分模型。"}</>;
}

function benchmarkSourceLabel(source: string) {
  if (source === "builtin") return "内置";
  if (source === "online") return "线上";
  return "线下";
}

export default function LaunchPage() {
  const lp = useLaunchPage();
  const judgeEnabled = Form.useWatch("judge_enabled", lp.form) ?? true;

  return (
    <DashboardPageShell
      centered
      title="发起评测"
      sub="选择 benchmark 与判分模型，配置运行参数后启动一次新的评测 run"
    >
      <div className="dash-launch">
        {lp.loadError ? (
          <AsyncLoadError message={lp.loadError} onRetry={lp.reloadLaunchData} />
        ) : (
        <Form
          form={lp.form}
          layout="vertical"
          className="dash-launch-form"
          onFinish={lp.onFinish}
          initialValues={{ judge_enabled: true, repeat: 1, limit: 0 }}
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
                extra={<FieldHint>评测将使用该 benchmark 中的全部或部分用例。</FieldHint>}
              >
                <Select
                  size="large"
                  placeholder="选择评测用例集"
                  onChange={lp.onBenchmarkChange}
                  options={lp.benchmarks.map((b) => ({
                    value: b.id,
                    label: `${b.name}（${benchmarkSourceLabel(b.source)} · ${b.case_count} 条）`,
                  }))}
                />
              </Form.Item>

              <Form.Item
                name="run_name"
                label="Run 名称"
                extra={<FieldHint>可选；留空则由系统自动命名。仅支持字母、数字、下划线。</FieldHint>}
              >
                <Input
                  size="large"
                  placeholder="如 doubao_breast_cancer"
                  maxLength={80}
                  showCount
                />
              </Form.Item>

              <Row gutter={16}>
                <Col xs={24} sm={12}>
                  <Form.Item
                    name="repeat"
                    label="重复次数（N-runs voting）"
                    extra={<FieldHint>同一用例重复跑 N 次，按多数票汇总稳定性。</FieldHint>}
                  >
                    <InputNumber min={1} size="large" style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12}>
                  <Form.Item
                    name="limit"
                    label="限制条数"
                    extra={<FieldHint>0 表示跑 benchmark 内全部用例；调试用可设小值。</FieldHint>}
                  >
                    <InputNumber min={0} size="large" style={{ width: "100%" }} />
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
                  <Checkbox.Group className="dash-option-cards" disabled={!lp.selectedBenchmark}>
                    {lp.levelOptions.map((opt) => (
                      <Checkbox key={opt.value} value={opt.value} className="dash-option-card">
                        <span className="dash-option-card__body">
                          <span className="dash-option-card__title">{opt.label}</span>
                          <span className="dash-option-card__desc">
                            仅跑该难度档位的用例 · {opt.count} 题
                          </span>
                        </span>
                      </Checkbox>
                    ))}
                  </Checkbox.Group>
                ) : (
                  <div className="dash-option-empty">
                    {lp.selectedBenchmark ? "该 benchmark 无 level 字段" : "选择 benchmark 后显示可选 Level"}
                  </div>
                )}
              </Form.Item>
            </section>

            <Divider className="dash-launch-divider" />

            <section className="dash-form-section">
              <h3 className="dash-form-card__title">判分配置</h3>
              <p className="dash-form-card__desc">
                配置 LLM-as-Judge 打分模型；关闭后仅跑 bot 留痕，不做自动判分。
              </p>

              <div className="dash-toggle-card">
                <div>
                  <div className="dash-toggle-card__title">启用 LLM 打分</div>
                  <div className="dash-toggle-card__desc">
                    开启后将对 bot 回复跑 HardGate + 规则 + LLM 判分链路。
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
                  placeholder={judgeEnabled ? "选择一个已配置的判分模型" : "已关闭 LLM 打分"}
                  options={lp.judgeModels.map((m) => ({
                    value: m.id,
                    label: `${m.name} · ${m.model}${m.has_api_key ? "" : "（未配 Key）"}`,
                  }))}
                />
              </Form.Item>

              {lp.selectedBenchmark && (
                <div className="dash-launch-summary">
                  <Text type="secondary">即将发起：</Text>
                  <span className="dash-chip">{lp.selectedBenchmark.name}</span>
                  <span className="dash-chip">
                    {lp.casesLoading ? "加载中…" : `${lp.estimatedCaseCount} 题`}
                  </span>
                </div>
              )}
            </section>

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
