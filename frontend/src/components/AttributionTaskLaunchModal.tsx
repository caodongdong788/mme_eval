import { Alert, Form, Modal, Select, Typography } from "antd";
import type { JudgeModel } from "../api";

export interface AttributionTaskLaunchModalProps {
  open: boolean;
  loading: boolean;
  requestedCount: number;
  failedCount: number;
  judgeModels: JudgeModel[];
  onCancel: () => void;
  onSubmit: (judgeModelId: number) => void;
}

export function AttributionTaskLaunchModal({
  open,
  loading,
  requestedCount,
  failedCount,
  judgeModels,
  onCancel,
  onSubmit,
}: AttributionTaskLaunchModalProps) {
  const [form] = Form.useForm<{ judge_model_id: number }>();
  const models = judgeModels.filter((model) => model.has_api_key);
  return (
    <Modal
      open={open}
      title="开始归因分析"
      okText="开始分析"
      cancelText="取消"
      confirmLoading={loading}
      okButtonProps={{ disabled: failedCount === 0 || models.length === 0 }}
      onCancel={onCancel}
      onOk={() => form.validateFields().then((values) => onSubmit(values.judge_model_id))}
      afterOpenChange={(visible) => {
        if (visible && !form.getFieldValue("judge_model_id") && models[0]) {
          form.setFieldValue("judge_model_id", models[0].id);
        }
      }}
    >
      <Typography.Paragraph type="secondary">
        当前筛选命中 {requestedCount} 条用例，其中 {failedCount} 条不合格将进入归因队列。
      </Typography.Paragraph>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 20 }}
        message="仅分析不合格用例"
        description="合格用例会自动跳过；系统同时最多分析 3 条，完成一条就立即展示一条结果。"
      />
      <Form form={form} layout="vertical">
        <Form.Item
          name="judge_model_id"
          label="归因分析模型"
          rules={[{ required: true, message: "请选择归因分析模型" }]}
        >
          <Select
            placeholder={models.length ? "选择模型" : "暂无已配置 API Key 的模型"}
            options={models.map((model) => ({
              value: model.id,
              label: `${model.name} · ${model.model}`,
            }))}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}
