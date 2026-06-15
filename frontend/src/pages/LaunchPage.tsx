import { Button, Card, Col, Form, Input, InputNumber, Row, Select, Space, Switch, Typography } from "antd";
import { RocketOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import { useLaunchPage } from "../hooks/useLaunchPage";

function judgeModelExtra(lp: ReturnType<typeof useLaunchPage>) {
  const defaultHint = lp.judgeDefaultModel ? `默认使用 ${lp.judgeDefaultModel}。` : "";
  if (lp.judgeModels.length === 0) {
    return (
      <Typography.Text type="secondary">
        还没有配置判分模型，去 <Link to="/judge-models">资源 · 判分模型</Link> 新增。
        {defaultHint}
      </Typography.Text>
    );
  }
  return (
    <Typography.Text type="secondary">
      可选；不选则{defaultHint || "沿用服务器 config.yaml 默认打分模型。"}
    </Typography.Text>
  );
}

export default function LaunchPage() {
  const lp = useLaunchPage();

  return (
    <Form
      form={lp.form}
      layout="vertical"
      onFinish={lp.onFinish}
      initialValues={{ judge_enabled: true, repeat: 1, limit: 0 }}
      style={{ maxWidth: 880 }}
    >
      <Space direction="vertical" size={16} style={{ display: "flex" }}>
        <Card title="发起评测">
          <Form.Item
            name="benchmark_id"
            label="选择 Benchmark"
            rules={[{ required: true, message: "请选择 benchmark" }]}
          >
            <Select
              placeholder="选择评测用例集"
              onChange={lp.onBenchmarkChange}
              options={lp.benchmarks.map((b) => ({
                value: b.id,
                label: `${b.name}（${b.source === "builtin" ? "内置" : "上传"} · ${b.case_count} 条）`,
              }))}
            />
          </Form.Item>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="run_name" label="Run 名称（可选）">
                <Input placeholder="如 doubao_breast_cancer" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="repeat" label="重复次数 (N-runs voting)">
                <InputNumber min={1} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="limit" label="限制条数 (0=全部)">
                <InputNumber min={0} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="levels" label="选择 Level（可选，多选；不选则默认全部）">
            <Select
              mode="multiple"
              allowClear
              placeholder={lp.selectedBenchmark ? "不选 = 运行全部 level" : "请先选择 benchmark"}
              disabled={!lp.selectedBenchmark}
              options={lp.levelOptions}
            />
          </Form.Item>
        </Card>

        <Card title="评测打分模型 (LLM-as-Judge)">
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="judge_enabled" label="启用 LLM 打分" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col span={16}>
              <Form.Item
                name="judge_model_id"
                label="打分模型（从「判分模型」配置中选择）"
                extra={judgeModelExtra(lp)}
              >
                <Select
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  placeholder="选择一个已配置的判分模型"
                  options={lp.judgeModels.map((m) => ({
                    value: m.id,
                    label: `${m.name} · ${m.model}${m.has_api_key ? "" : "（未配 Key）"}`,
                  }))}
                />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" loading={lp.submitting} icon={<RocketOutlined />}>
              发起评测
            </Button>
          </Form.Item>
        </Card>
      </Space>
    </Form>
  );
}
