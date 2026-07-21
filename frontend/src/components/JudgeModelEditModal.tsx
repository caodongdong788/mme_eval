import {
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Slider,
} from "antd";
import type { FormInstance } from "antd";

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
              <Input placeholder="https://api.openai.com/v1" />
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
            <Form.Item label="回复随机性">
              <Row gutter={12} align="middle">
                <Col flex="auto">
                  <Form.Item name="temperature" noStyle>
                    <Slider min={0} max={2} step={0.1} />
                  </Form.Item>
                </Col>
                <Col>
                  <Form.Item name="temperature" noStyle>
                    <InputNumber min={0} max={2} step={0.1} />
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
