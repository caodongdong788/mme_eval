import { Alert, Form, Modal, Select, Typography } from "antd";
import { useEffect, useMemo } from "react";
import type { JudgeModel } from "../api";

export type AttributionModelSelectionMode = "start" | "rerun" | "resume";

export interface AttributionTaskLaunchModalProps {
  open: boolean;
  loading: boolean;
  requestedCount: number;
  failedCount: number;
  judgeModels: JudgeModel[];
  mode?: AttributionModelSelectionMode;
  defaultJudgeModelId?: number;
  onCancel: () => void;
  onSubmit: (judgeModelId: number) => void;
}

export function AttributionTaskLaunchModal({
  open,
  loading,
  requestedCount,
  failedCount,
  judgeModels,
  mode = "start",
  defaultJudgeModelId,
  onCancel,
  onSubmit,
}: AttributionTaskLaunchModalProps) {
  const [form] = Form.useForm<{ judge_model_id: number }>();
  const models = useMemo(
    () => judgeModels.filter((model) => model.has_api_key),
    [judgeModels]
  );
  const isStart = mode === "start";
  const title = isStart ? "开始归因分析" : mode === "resume" ? "继续归因" : "重新归因";
  const okText = isStart ? "开始分析" : mode === "resume" ? "继续归因" : "开始重试";

  useEffect(() => {
    if (!open) return;
    const selected = models.some((model) => model.id === defaultJudgeModelId)
      ? defaultJudgeModelId
      : models[0]?.id;
    form.setFieldValue("judge_model_id", selected);
  }, [defaultJudgeModelId, form, models, open]);

  return (
    <Modal
      open={open}
      title={title}
      okText={okText}
      cancelText="取消"
      confirmLoading={loading}
      okButtonProps={{ disabled: (isStart && failedCount === 0) || models.length === 0 }}
      onCancel={onCancel}
      onOk={() => form.validateFields().then((values) => onSubmit(values.judge_model_id))}
    >
      {isStart ? (
        <>
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
        </>
      ) : (
        <Typography.Paragraph type="secondary">
          本次将使用所选模型分析 {requestedCount} 条用例。已完成的历史归因结果会保留不变。
        </Typography.Paragraph>
      )}
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
