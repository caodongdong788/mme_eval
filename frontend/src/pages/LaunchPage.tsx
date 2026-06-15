import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Switch,
  Typography,
  message,
} from "antd";
import { RocketOutlined } from "@ant-design/icons";
import { Link, useNavigate } from "react-router-dom";
import { api, Benchmark, JudgeModel, RunCreatePayload, selectableBenchmarks } from "../api";
import { formatApiError } from "../utils/apiError";

export default function LaunchPage() {
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [judgeModels, setJudgeModels] = useState<JudgeModel[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  const [levelOptions, setLevelOptions] = useState<{ value: string; label: string }[]>([]);
  const benchmarkId = Form.useWatch("benchmark_id", form);

  useEffect(() => {
    api.listBenchmarks().then((all) => setBenchmarks(selectableBenchmarks(all)));
    api.listJudgeModels().then(setJudgeModels);
  }, []);

  const selectedBenchmark = useMemo(
    () => benchmarks.find((b) => b.id === benchmarkId),
    [benchmarks, benchmarkId]
  );

  // 选定 benchmark 后，从其用例中提取实际包含的 level 作为下拉选项
  const onBenchmarkChange = async (id: number) => {
    form.setFieldValue("levels", []);
    setLevelOptions([]);
    const cases = await api.getBenchmarkCases(id);
    const levels = Array.from(new Set(cases.map((c) => c.level).filter(Boolean))).sort();
    setLevelOptions(levels.map((l) => ({ value: l, label: l })));
  };

  const onFinish = async (values: any) => {
    const payload: RunCreatePayload = {
      benchmark_id: values.benchmark_id,
      run_name: values.run_name || undefined,
      levels: values.levels || [],
      limit: values.limit || 0,
      repeat: values.repeat || undefined,
      judge: { enabled: values.judge_enabled },
      judge_model_id: values.judge_model_id || undefined,
    };
    setSubmitting(true);
    try {
      const run = await api.createRun(payload);
      message.success(`评测已发起：#${run.id}`);
      navigate(`/runs`);
    } catch (e: any) {
      message.error(formatApiError(e, "发起失败"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={onFinish}
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
              onChange={onBenchmarkChange}
              options={benchmarks.map((b) => ({
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
              placeholder={selectedBenchmark ? "不选 = 运行全部 level" : "请先选择 benchmark"}
              disabled={!selectedBenchmark}
              options={levelOptions}
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
                extra={
                  judgeModels.length === 0 ? (
                    <Typography.Text type="secondary">
                      还没有配置判分模型，去 <Link to="/judge-models">资源 · 判分模型</Link> 新增；不选则用服务器默认配置。
                    </Typography.Text>
                  ) : (
                    "不选则沿用服务器 config.yaml 默认打分模型"
                  )
                }
              >
                <Select
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  placeholder="选择一个已配置的判分模型"
                  options={judgeModels.map((m) => ({
                    value: m.id,
                    label: `${m.name} · ${m.model}${m.has_api_key ? "" : "（未配 Key）"}`,
                  }))}
                />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" loading={submitting} icon={<RocketOutlined />}>
              发起评测
            </Button>
          </Form.Item>
        </Card>
      </Space>
    </Form>
  );
}
