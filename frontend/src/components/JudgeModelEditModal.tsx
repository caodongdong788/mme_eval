import {
  Button,
  Col,
  Divider,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Slider,
  Space,
  Typography,
} from "antd";
import type { FormInstance } from "antd";

type Props = {
  open: boolean;
  editId: number | null;
  saving: boolean;
  optimizing: boolean;
  form: FormInstance;
  onCancel: () => void;
  onSubmit: () => void;
  onOptimizePrompt: () => void;
};

export function JudgeModelEditModal({
  open,
  editId,
  saving,
  optimizing,
  form,
  onCancel,
  onSubmit,
  onOptimizePrompt,
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
      width={960}
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <div className="judge-model-editor">
          <div className="judge-model-editor__prompt">
            <div className="judge-model-editor__prompt-head">
              <Typography.Text strong>Judge Prompt</Typography.Text>
              <Button type="primary" loading={optimizing} onClick={onOptimizePrompt}>
                Prompt 质检
              </Button>
            </div>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 8, fontSize: 13 }}>
              新建时预填系统内置模板。保存前须含占位符 {"{conversation}"}、{"{rubric_text}"}、
              {"{tool_context}"}，且说明 JSON 输出含 scores / reasons / flags；不合规可用「Prompt 质检」修正。
            </Typography.Paragraph>
            <Form.Item name="prompt_template" style={{ marginBottom: 0 }}>
              <Input.TextArea
                rows={18}
                placeholder="LLM-as-Judge prompt 模板…"
                className="judge-model-editor__textarea"
              />
            </Form.Item>
          </div>

          <div className="judge-model-editor__config">
            <Form.Item name="name" label="配置名称" rules={[{ required: true, message: "请输入名称" }]}>
              <Input placeholder="如：强判官-gpt5.1" />
            </Form.Item>
            <Space style={{ display: "flex" }} align="start">
              <Form.Item name="provider" label="Provider" style={{ flex: 1 }}>
                <Select
                  options={[
                    { value: "openai", label: "openai" },
                    { value: "azure", label: "azure" },
                  ]}
                />
              </Form.Item>
              <Form.Item
                name="model"
                label="模型"
                style={{ flex: 2 }}
                rules={[{ required: true, message: "请输入模型名" }]}
              >
                <Input placeholder="如 gpt-5.1 / gpt-4o" />
              </Form.Item>
            </Space>
            <Form.Item name="base_url" label="Base URL（可选）">
              <Input placeholder="https://api.openai.com/v1" />
            </Form.Item>
            <Form.Item name="api_version" label="API Version（azure，可选）">
              <Input placeholder="2024-02-01" />
            </Form.Item>
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
            <Form.Item
              name="api_key"
              label={editId != null ? "API Key（留空=保持不变）" : "API Key"}
              extra="仅写入后端、不回显；发起评测时由服务端注入运行期。"
            >
              <Input.Password placeholder={editId != null ? "留空则不修改" : "sk-..."} autoComplete="off" />
            </Form.Item>

            <Divider orientation="left" plain style={{ marginTop: 4 }}>
              <Typography.Text type="secondary">Pairwise 对比</Typography.Text>
            </Divider>
            <Form.Item
              name="pairwise_concurrency"
              label="对比并发（题间）"
              rules={[{ required: true, message: "请输入并发度" }]}
              extra="仅作用于 Pairwise 对比：同时比较几道用例（题内两次裁判默认并行）。不影响主评测端并发。"
            >
              <InputNumber min={1} max={32} step={1} style={{ width: "100%" }} placeholder="默认 4" />
            </Form.Item>
          </div>
        </div>
      </Form>
    </Modal>
  );
}
