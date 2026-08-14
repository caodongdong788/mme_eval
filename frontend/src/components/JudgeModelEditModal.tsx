import {
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Slider,
  Switch,
} from "antd";
import type { FormInstance } from "antd";
import { useEffect } from "react";

const KIMI_K3_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1";

function isKimiK3Model(model: unknown): boolean {
  const normalized = String(model ?? "").trim().toLowerCase();
  return normalized === "kimi-k3" || normalized === "kimi/kimi-k3";
}

type Props = {
  open: boolean;
  editId: number | null;
  saving: boolean;
  form: FormInstance;
  onCancel: () => void;
  onSubmit: () => void;
};

export function JudgeModelEditModal({
  open,
  editId,
  saving,
  form,
  onCancel,
  onSubmit,
}: Props) {
  const model = Form.useWatch("model", form);
  const isKimiK3 = isKimiK3Model(model);

  useEffect(() => {
    if (isKimiK3) {
      form.setFieldsValue({
        provider: form.getFieldValue("provider") || "openai",
        base_url: form.getFieldValue("base_url") || KIMI_K3_DASHSCOPE_BASE_URL,
        temperature: 1,
        enable_thinking: true,
      });
    }
  }, [form, isKimiK3]);

  return (
    <Modal
      title={editId != null ? "编辑判分模型" : "新增判分模型"}
      open={open}
      onOk={onSubmit}
      confirmLoading={saving}
      onCancel={onCancel}
      okText="保存"
      cancelText="取消"
      width={760}
      className="judge-model-modal"
      style={{ top: 32 }}
      destroyOnClose
    >
      <Form form={form} layout="vertical" className="judge-model-form">
        <Form.Item name="name" label="配置名称" rules={[{ required: true, message: "请输入名称" }]}>
          <Input placeholder="如：强判官-gpt5.1" />
        </Form.Item>
        <Row gutter={16}>
          <Col xs={24} sm={8}>
            <Form.Item name="provider" label="Provider">
              <Select
                options={[
                  { value: "openai", label: "openai" },
                  { value: "azure", label: "azure" },
                  { value: "codex", label: "Codex 本地网关" },
                ]}
              />
            </Form.Item>
          </Col>
          <Col xs={24} sm={16}>
            <Form.Item
              name="model"
              label="模型"
              rules={[{ required: true, message: "请输入模型名" }]}
            >
              <Input placeholder="如 gpt-5.1 / gpt-4o" />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col xs={24} sm={16}>
            <Form.Item name="base_url" label="Base URL（可选）">
              <Input placeholder="https://api.openai.com/v1；Codex 网关示例：http://127.0.0.1:8787/v1" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={8}>
            <Form.Item name="api_version" label="API Version（Azure，可选）">
              <Input placeholder="2024-02-01" />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col xs={24} sm={12}>
            <Form.Item
              label="回复随机性"
              extra={isKimiK3 ? "Kimi K3 使用官方默认值 1.0，无法修改。" : undefined}
            >
              <Row gutter={12} align="middle">
                <Col flex="auto">
                  <Form.Item name="temperature" noStyle>
                    <Slider min={0} max={2} step={0.1} disabled={isKimiK3} />
                  </Form.Item>
                </Col>
                <Col>
                  <Form.Item name="temperature" noStyle>
                    <InputNumber min={0} max={2} step={0.1} disabled={isKimiK3} />
                  </Form.Item>
                </Col>
              </Row>
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item
              name="pairwise_concurrency"
              label="Pairwise 对比并发（题间）"
              rules={[{ required: true, message: "请输入并发度" }]}
              extra="同时比较的用例数，不影响主评测并发。"
            >
              <InputNumber
                min={1}
                max={32}
                step={1}
                style={{ width: "100%" }}
                placeholder="默认 4"
              />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item
          name="enable_thinking"
          label={isKimiK3 ? "思考模式" : "启用思考"}
          valuePropName="checked"
          extra={
            isKimiK3
              ? "Kimi K3 为仅思考模型，系统会以官方默认推理配置调用。"
              : "DashScope 等兼容接口可通过该选项控制是否输出思考过程。"
          }
        >
          <Switch disabled={isKimiK3} />
        </Form.Item>
        <Form.Item
          name="api_key"
          label={editId != null ? "API Key（留空=保持不变）" : "API Key"}
          extra="仅写入后端、不回显；发起评测时由服务端注入运行期。"
        >
          <Input.Password
            placeholder={editId != null ? "留空则不修改" : "sk-..."}
            autoComplete="off"
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}
