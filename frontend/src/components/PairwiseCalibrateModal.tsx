import { useEffect, useState } from "react";
import { Alert, Form, Input, Modal, Radio, Select, Space, Typography, message } from "antd";
import {
  api,
  type PairwiseCalibratePayload,
  type PairwiseCaseVerdict,
} from "../api/index";
import { DIM_LABEL } from "../labels";
import { formatApiError } from "../utils/apiError";

const DIMS = ["safety", "function", "experience"] as const;
const SIDE_OPTS = [
  { value: "A", label: "A 更好" },
  { value: "B", label: "B 更好" },
  { value: "tie", label: "持平" },
];

type Props = {
  open: boolean;
  comparisonId: number;
  verdict: PairwiseCaseVerdict | null;
  onClose: () => void;
  onSaved: () => void;
};

export default function PairwiseCalibrateModal({
  open,
  comparisonId,
  verdict,
  onClose,
  onSaved,
}: Props) {
  const [form] = Form.useForm<PairwiseCalibratePayload>();
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !verdict) return;
    form.setFieldsValue({
      winner: verdict.winner,
      reason: verdict.reason,
      dimension_winners: {
        safety: (verdict.dimension_winners?.safety as "A" | "B" | "tie") || "tie",
        function: (verdict.dimension_winners?.function as "A" | "B" | "tie") || "tie",
        experience: (verdict.dimension_winners?.experience as "A" | "B" | "tie") || "tie",
      },
    });
  }, [open, verdict, form]);

  const submit = async () => {
    if (!verdict) return;
    let v: PairwiseCalibratePayload;
    try {
      v = await form.validateFields();
    } catch {
      return;
    }
    setSaving(true);
    try {
      await api.calibratePairwiseVerdict(comparisonId, verdict.sample_id, {
        winner: v.winner,
        reason: (v.reason || "").trim(),
        dimension_winners: v.dimension_winners || {},
      });
      message.success("已保存人工校准，报告统计已更新");
      onSaved();
      onClose();
    } catch (e: any) {
      message.error(formatApiError(e, "保存失败"));
    } finally {
      setSaving(false);
    }
  };

  const resetMachine = async () => {
    if (!verdict) return;
    try {
      await api.resetPairwiseCalibration(comparisonId, verdict.sample_id);
      message.success("已恢复机器判定");
      onSaved();
      onClose();
    } catch (e: any) {
      message.error(formatApiError(e, "恢复失败"));
    }
  };

  return (
    <Modal
      title="人工校准"
      open={open}
      onCancel={onClose}
      onOk={submit}
      confirmLoading={saving}
      okText="保存校准"
      cancelText="取消"
      width={520}
      destroyOnClose
    >
      {verdict?.human_calibrated && verdict.auto_winner != null && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message={`机器原判：${verdict.auto_winner === "A" ? "A 更好" : verdict.auto_winner === "B" ? "B 更好" : "持平"}`}
          description={verdict.auto_reason || undefined}
        />
      )}
      <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
        校准后将覆盖本条的有效结论/维度/理由，置信显示为「人工校准」，报告汇总会联动重算。
      </Typography.Paragraph>
      <Form form={form} layout="vertical">
        <Form.Item
          name="winner"
          label="结论"
          rules={[{ required: true, message: "请选择结论" }]}
        >
          <Radio.Group>
            <Radio.Button value="A">A 更好</Radio.Button>
            <Radio.Button value="B">B 更好</Radio.Button>
            <Radio.Button value="tie">持平</Radio.Button>
          </Radio.Group>
        </Form.Item>
        <Space style={{ display: "flex", width: "100%" }} align="start">
          {DIMS.map((dim) => (
            <Form.Item
              key={dim}
              name={["dimension_winners", dim]}
              label={`${DIM_LABEL[dim]}维度`}
              style={{ flex: 1 }}
              initialValue="tie"
            >
              <Select options={SIDE_OPTS} />
            </Form.Item>
          ))}
        </Space>
        <Form.Item name="reason" label="理由">
          <Input.TextArea
            placeholder="说明人工校准依据（可选）"
            autoSize={{ minRows: 2, maxRows: 5 }}
            maxLength={500}
            showCount
          />
        </Form.Item>
      </Form>
      {verdict?.human_calibrated && (
        <Typography.Link type="secondary" onClick={resetMachine}>
          恢复机器判定
        </Typography.Link>
      )}
    </Modal>
  );
}
